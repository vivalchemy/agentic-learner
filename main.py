import os
import streamlit as st
import asyncio
from typing import List, Dict, Optional
import json
from agno.agent import Agent
from agno.models.google import Gemini
import scrapetube
from dotenv import load_dotenv
from dataclasses import dataclass
from enum import Enum

load_dotenv()

# constants
class Model(Enum):
    FAST = "gemini-2.5-flash"
    PRO = "gemini-2.5-pro"

MAX_WIDTH = 720

# config & enums
class AppState(Enum):
    TOPIC_INPUT = "topic_input"
    FETCH_CONTENT = "fetch_content"
    LEARNING = "learning"
    GENERATE_QUIZ = "generate_quiz"
    TAKE_QUIZ = "take_quiz"
    EVALUATE = "evaluate"


@dataclass
class SessionData:
    current_step: str = AppState.TOPIC_INPUT.value
    topic: str = ""
    videos: Optional[List[Dict]] = None
    current_video_index: int = 0
    documentation: str = ""
    quiz: Optional[List[Dict]] = None
    user_answers: Optional[Dict] = None
    weak_areas: Optional[List[str]] = None
    quiz_attempt: int = 1
    mastery_achieved: bool = False
    chat_history: Optional[List[Dict]] = None
    related_topics: Optional[List[str]] = None

    def __post_init__(self):
        if self.videos is None:
            self.videos = []
        if self.quiz is None:
            self.quiz = []
        if self.user_answers is None:
            self.user_answers = {}
        if self.weak_areas is None:
            self.weak_areas = []
        if self.chat_history is None:
            self.chat_history = []
        if self.related_topics is None:
            self.related_topics = []


# agents
class TopicSelectorAgent:

    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Topic Selector",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Topic Selection Expert",
            instructions=[
                "Analyze user input and extract or refine the learning topic",
                "Ensure the topic is clear, specific, and suitable for learning",
                "If topic is vague, make it more specific and educational",
            ],
            markdown=True,
        )

    async def select_topic(self, user_input: str) -> str:
        response = await self.agent.arun(
            f"Extract and refine a clear learning topic from: '{user_input}'. "
            f"Return ONLY the topic name, nothing else."
        )
        content = response.content if response.content is not None else "General Topic"
        return content.strip()


class VideoRetrieverAgent:

    @staticmethod
    def fetch_videos(topic: str, limit: int = 10) -> List[Dict]:
        try:
            videos = []
            video_results = scrapetube.get_search(topic, limit=limit)

            for video in video_results:
                video_id = video.get("videoId")
                if not video_id:
                    continue

                title = (
                    video.get("title", {})
                    .get("runs", [{}])[0]
                    .get("text", "No title")
                )

                channel_name = "Unknown"
                if "ownerText" in video and "runs" in video["ownerText"]:
                    channel_name = video["ownerText"]["runs"][0].get("text", "Unknown")

                videos.append({
                    "title": title,
                    "link": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "channel": channel_name,
                })

                if len(videos) >= limit:
                    break

            return videos
        except Exception as e:
            st.error(f"Error fetching videos: {e}")
            return []


class DocGeneratorAgent:
    """Agent for generating educational documentation"""
    
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Documentation Generator",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Educational Content Creator",
            instructions=[
                "Research and compile comprehensive educational documentation",
                "Structure content with clear sections: Introduction, Key Concepts, Examples, Summary",
                "Use simple language suitable for learners",
                "Include practical examples and real-world applications",
                "Organize information logically with proper headings",
                "Don't include anything other than the information from your side as an affirmation to the prompt"
            ],
            markdown=True,
        )

    async def generate_docs(self, topic: str) -> str:
        response = await self.agent.arun(
            f"Create comprehensive educational documentation about '{topic}'. "
            f"Include: 1) Introduction, 2) Core Concepts (with definitions), "
            f"3) Practical Examples, 4) Key Takeaways. "
            f"Make it detailed but easy to understand."
        )
        return (
            response.content
            if response.content is not None
            else "Documentation not available."
        )


class QuizGeneratorAgent:
    """Agent for generating assessment quizzes"""
    
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Quiz Generator",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Assessment Creator",
            instructions=[
                "Generate multiple-choice questions based on documentation",
                "Create 5 questions covering different aspects of the topic",
                "Each question should have 4 options with only one correct answer",
                "Include questions of varying difficulty",
                "Format as JSON array",
            ],
            markdown=False,
        )

    async def generate_quiz(
        self, documentation: str, weak_areas: Optional[List[str]] = None
    ) -> List[Dict]:
        focus = ""
        if weak_areas:
            focus = f" Focus more on these weak areas: {', '.join(weak_areas)}."

        response = await self.agent.arun(
            f"Based on this documentation:\n\n{documentation}\n\n"
            f"Generate 5 multiple-choice questions.{focus} "
            f"Return ONLY a valid JSON array in this exact format:\n"
            f'[{{"question": "...", "options": ["A", "B", "C", "D"], "correct": 0, "explanation": "..."}}]\n'
            f"The 'correct' field should be the index (0-3) of the correct option."
        )

        try:
            content = response.content
            if content is None:
                st.error("Quiz generation returned no content")
                return []

            content = content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            content = content.strip()

            quiz_data = json.loads(content)
            return quiz_data
        except Exception as e:
            st.error(f"Error parsing quiz: {e}")
            return []


class EvaluatorAgent:
    """Agent for evaluating quiz performance and providing feedback"""
    
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Learning Coach",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Learning Assessment Expert",
            instructions=[
                "Evaluate student answers and identify knowledge gaps",
                "Determine which concepts need more focus",
                "Decide if student has achieved mastery (80%+ correct)",
                "Provide constructive feedback",
                "Be encouraging but honest about areas needing improvement",
            ],
            markdown=True,
        )

    async def evaluate(
        self, quiz: List[Dict], answers: Dict, documentation: str
    ) -> Dict:
        correct_count = 0
        total = len(quiz)
        weak_topics = []

        for i, q in enumerate(quiz):
            user_answer = answers.get(i, -1)
            if user_answer == q["correct"]:
                correct_count += 1
            else:
                weak_topics.append(q["question"])

        score_percent = (correct_count / total * 100) if total > 0 else 0
        mastery = score_percent >= 80

        feedback_prompt = (
            f"A student scored {correct_count}/{total} ({score_percent:.1f}%) on a quiz about the topic. "
            f"Questions they got wrong: {weak_topics if weak_topics else 'None'}. "
            f"Documentation: {documentation[:500]}... "
            f"Provide: 1) Encouraging feedback, 2) Specific areas to review, 3) Whether they achieved mastery."
        )

        response = await self.agent.arun(feedback_prompt)
        feedback_content = (
            response.content
            if response.content is not None
            else "Feedback not available."
        )

        return {
            "score": correct_count,
            "total": total,
            "percentage": score_percent,
            "mastery": mastery,
            "feedback": feedback_content,
            "weak_areas": weak_topics,
        }


class QAAgent:
    """Agent for answering questions about the topic"""
    
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Q&A Assistant",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Educational Q&A Expert",
            instructions=[
                "Answer questions based on the provided documentation",
                "Provide clear, concise, and educational answers",
                "Use examples when helpful",
                "If question is outside documentation scope, mention it but try to help anyway",
                "Be encouraging and supportive",
            ],
            markdown=True,
        )

    async def answer_question(self, question: str, documentation: str) -> str:
        response = await self.agent.arun(
            f"Based on this documentation:\n\n{documentation}\n\n"
            f"Answer this question: {question}\n\n"
            f"Provide a clear, educational answer."
        )
        return (
            response.content
            if response.content is not None
            else "Answer not available."
        )


class RelatedTopicsAgent:
    """Agent for suggesting related learning topics"""
    
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Related Topics Finder",
            model=Gemini(id=Model.FAST.value, api_key=api_key),
            role="Learning Path Expert",
            instructions=[
                "Suggest related topics for deeper learning",
                "Topics should build on or complement the main topic",
                "Provide 5 specific, actionable topic suggestions",
                "Each topic should be clearly described",
            ],
            markdown=False,
        )

    async def get_related_topics(self, topic: str, documentation: str) -> List[str]:
        response = await self.agent.arun(
            f"The student has mastered '{topic}'. "
            f"Based on this documentation:\n\n{documentation[:500]}...\n\n"
            f"Suggest 5 related topics they should learn next. "
            f"Return ONLY a numbered list of topics, one per line."
        )

        topics = []
        content = response.content if response.content is not None else ""
        for line in content.split("\n"):
            line = line.strip()
            if line and (
                line[0].isdigit() or line.startswith("-") or line.startswith("*")
            ):
                topic_text = line.lstrip("0123456789.-* ").strip()
                if topic_text:
                    topics.append(topic_text)

        return topics[:5]


class AgentManager:
    """Centralized manager for all AI agents"""
    
    def __init__(self, api_key: str):
        self.topic_agent = TopicSelectorAgent(api_key)
        self.video_agent = VideoRetrieverAgent()
        self.doc_agent = DocGeneratorAgent(api_key)
        self.quiz_agent = QuizGeneratorAgent(api_key)
        self.eval_agent = EvaluatorAgent(api_key)
        self.qa_agent = QAAgent(api_key)
        self.related_agent = RelatedTopicsAgent(api_key)


# state machine

class LearningStateMachine:
    """State machine to manage application flow and transitions"""
    
    def __init__(self, agents: AgentManager):
        self.agents = agents
        self._initialize_session_state()

    def _initialize_session_state(self):
        """Initialize all session state variables"""
        defaults = SessionData()
        for key, value in defaults.__dict__.items():
            if key not in st.session_state:
                st.session_state[key] = value

    def transition_to(self, new_state: AppState):
        """Transition to a new state"""
        st.session_state.current_step = new_state.value
        st.rerun()

    def reset_state(self):
        """Reset all session state"""
        for key in list(st.session_state.keys()):
            del st.session_state[key]

    def run(self):
        """Main state machine execution"""
        current_state = st.session_state.current_step

        state_handlers = {
            AppState.TOPIC_INPUT.value: self.handle_topic_input,
            AppState.FETCH_CONTENT.value: self.handle_fetch_content,
            AppState.LEARNING.value: self.handle_learning,
            AppState.GENERATE_QUIZ.value: self.handle_generate_quiz,
            AppState.TAKE_QUIZ.value: self.handle_take_quiz,
            AppState.EVALUATE.value: self.handle_evaluate,
        }

        handler = state_handlers.get(current_state)
        if handler:
            handler()
        else:
            st.error(f"Unknown state: {current_state}")

# state handlers

    def handle_topic_input(self):
        """Handle topic input state"""
        st.header("Select the Topic You want to Learn")
        user_topic = st.text_input(
            "What would you like to learn today?",
            placeholder="e.g., Machine Learning, Python Lists, Photosynthesis",
        )

        if st.button("🚀 Start Learning", type="primary"):
            if user_topic:
                with st.spinner("Analyzing topic..."):
                    topic = asyncio.run(self.agents.topic_agent.select_topic(user_topic))
                    st.session_state.topic = topic
                    self.transition_to(AppState.FETCH_CONTENT)
            else:
                st.error("Please enter a topic")

    def handle_fetch_content(self):
        """Handle content fetching state"""
        st.header(f"Learning: {st.session_state.topic}")

        with st.spinner("Fetching resources..."):
            if not st.session_state.videos:
                videos = self.agents.video_agent.fetch_videos(
                    st.session_state.topic, limit=10
                )
                st.session_state.videos = videos
                st.session_state.current_video_index = 0

            if not st.session_state.documentation:
                docs = asyncio.run(
                    self.agents.doc_agent.generate_docs(st.session_state.topic)
                )
                st.session_state.documentation = docs

            self.transition_to(AppState.LEARNING)

    def handle_learning(self):
        """Handle learning state with videos, docs, and Q&A"""
        st.header(f"Learning: {st.session_state.topic}")

        tab1, tab2 = st.tabs(["Study Material", "Chatbot"])

        with tab1:
            self._render_study_material()

        with tab2:
            self._render_chatbot()

    def _render_study_material(self):
        """Render study material tab (videos and documentation)"""
        # Video Section
        if st.session_state.videos:
            st.subheader("Recommended Video")
            current_video = st.session_state.videos[st.session_state.current_video_index]

            st.video(current_video["link"], width=MAX_WIDTH)
            st.markdown(f"**{current_video['title']}**")
            st.markdown(f"📺 *{current_video['channel']}*")

            col1, col2 = st.columns([1, 4])
            with col1:
                if st.button("Previous Video"):
                    st.session_state.current_video_index = (
                        st.session_state.current_video_index - 1
                    ) % len(st.session_state.videos)
                    st.rerun()
            with col2:
                if st.button("Next Video"):
                    st.session_state.current_video_index = (
                        st.session_state.current_video_index + 1
                    ) % len(st.session_state.videos)
                    st.rerun()

        st.markdown("---")

        # Documentation Section
        st.subheader("Study Material")
        st.markdown(st.session_state.documentation, width=MAX_WIDTH)

        st.markdown("---")

        if st.button("Take a quiz", type="primary", use_container_width=True):
            self.transition_to(AppState.GENERATE_QUIZ)

    def _render_chatbot(self):
        """Render Q&A chatbot tab"""
        st.subheader("Ask Questions About This Topic")

        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat["question"])
            with st.chat_message("assistant"):
                st.markdown(chat["answer"])

        user_question = st.chat_input("Ask a question about the topic...")

        if user_question:
            with st.chat_message("user"):
                st.write(user_question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    answer = asyncio.run(
                        self.agents.qa_agent.answer_question(
                            user_question, st.session_state.documentation
                        )
                    )
                    st.markdown(answer)

            st.session_state.chat_history.append(
                {"question": user_question, "answer": answer}
            )
            st.rerun()

    def handle_generate_quiz(self):
        """Handle quiz generation state"""
        with st.spinner("Preparing your quiz..."):
            weak_areas_to_pass = (
                st.session_state.weak_areas if st.session_state.weak_areas else None
            )
            quiz = asyncio.run(
                self.agents.quiz_agent.generate_quiz(
                    st.session_state.documentation, weak_areas_to_pass
                )
            )
            st.session_state.quiz = quiz
            st.session_state.user_answers = {}
            self.transition_to(AppState.TAKE_QUIZ)

    def handle_take_quiz(self):
        """Handle quiz taking state"""
        st.header(f"📝 Quiz - Attempt #{st.session_state.quiz_attempt}")
        st.markdown(f"**Topic:** {st.session_state.topic}")

        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz):
                st.markdown(f"**Question {i + 1}:** {q['question']}")
                answer = st.radio(
                    "Select your answer:",
                    options=range(len(q["options"])),
                    format_func=lambda x, opts=q["options"]: opts[x],
                    key=f"q_{i}",
                )
                st.session_state.user_answers[i] = answer
                st.markdown("---")

            submitted = st.form_submit_button("Submit Quiz", type="primary")

            if submitted:
                self.transition_to(AppState.EVALUATE)

    def handle_evaluate(self):
        """Handle evaluation state"""
        with st.spinner("Evaluating your answers..."):
            results = asyncio.run(
                self.agents.eval_agent.evaluate(
                    st.session_state.quiz,
                    st.session_state.user_answers,
                    st.session_state.documentation,
                )
            )

            if results["mastery"] and not st.session_state.related_topics:
                st.session_state.related_topics = asyncio.run(
                    self.agents.related_agent.get_related_topics(
                        st.session_state.topic, st.session_state.documentation
                    )
                )

            self._render_quiz_results(results)

    def _render_quiz_results(self, results: Dict):
        """Render quiz results and feedback"""
        st.header("📊 Quiz Results")

        col1, col2, col3 = st.columns(3)
        col1.metric("Score", f"{results['score']}/{results['total']}")
        col2.metric("Percentage", f"{results['percentage']:.1f}%")
        col3.metric("Status", "✅ Mastery" if results["mastery"] else "📚 Keep Learning")

        st.markdown("---")
        st.subheader("Detailed Feedback")
        st.markdown(results["feedback"])

        st.markdown("---")
        st.subheader("Answer Review")
        for i, q in enumerate(st.session_state.quiz):
            user_ans = st.session_state.user_answers.get(i, -1)
            correct = user_ans == q["correct"]

            with st.expander(
                f"{'✅' if correct else '❌'} Question {i + 1}: {q['question'][:50]}..."
            ):
                st.markdown(
                    f"**Your answer:** {q['options'][user_ans] if user_ans >= 0 else 'Not answered'}"
                )
                st.markdown(f"**Correct answer:** {q['options'][q['correct']]}")
                st.markdown(f"**Explanation:** {q.get('explanation', 'N/A')}")

        if results["mastery"]:
            self._render_mastery_section()
        else:
            self._render_retry_section(results)

    def _render_mastery_section(self):
        """Render mastery achievement section"""
        st.success("🎉 Congratulations! You've mastered this topic!")
        st.balloons()

        st.markdown("---")
        st.subheader("Continue Your Learning Journey")
        st.markdown("Here are some related topics you might want to explore next:")

        for i, related_topic in enumerate(st.session_state.related_topics, 1):
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"**{i}.** {related_topic}")
            with col2:
                if st.button("Learn", key=f"related_{i}"):
                    self.reset_state()
                    st.session_state.current_step = AppState.FETCH_CONTENT.value
                    st.session_state.topic = related_topic
                    st.rerun()

        st.markdown("---")
        if st.button("Learn Another Topic", use_container_width=True):
            self.reset_state()
            st.rerun()

    def _render_retry_section(self, results: Dict):
        """Render retry options for non-mastery"""
        st.warning("📚 You need more practice. Let's focus on your weak areas!")
        st.session_state.weak_areas = results["weak_areas"][:3]
        st.session_state.quiz_attempt += 1

        col1, col2 = st.columns(2)
        with col1:
            if st.button(
                "🔄 Retake Quiz (Focused on Weak Areas)",
                type="primary",
                use_container_width=True,
            ):
                self.transition_to(AppState.GENERATE_QUIZ)
        with col2:
            if st.button("📚 Study Again", use_container_width=True):
                self.transition_to(AppState.LEARNING)


# MAIN APPLICATION
def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="AI Learning Assistant",
        page_icon="🎓",
        layout="wide"
    )

    st.title("🎓 Agentic Learner")

    # API Key validation
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
        if not api_key:
            st.warning("Please enter your Gemini API key in the sidebar to continue")
            st.info("Get API key from: https://aistudio.google.com/app/apikey")
            return

    # Initialize agents and state machine
    agents = AgentManager(api_key)
    state_machine = LearningStateMachine(agents)

    # Run state machine
    state_machine.run()


if __name__ == "__main__":
    main()

