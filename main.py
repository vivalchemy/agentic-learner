import os
import streamlit as st
import asyncio
from typing import List, Dict, Optional
import json
from agno.agent import Agent
from agno.models.google import Gemini
import scrapetube
from dotenv import load_dotenv

load_dotenv()

# Set page config
st.set_page_config(page_title="AI Learning Assistant", page_icon="🎓", layout="wide")

# Initialize session state
if "current_step" not in st.session_state:
    st.session_state.current_step = "topic_input"
if "topic" not in st.session_state:
    st.session_state.topic = ""
if "videos" not in st.session_state:
    st.session_state.videos = []
if "current_video_index" not in st.session_state:
    st.session_state.current_video_index = 0
if "documentation" not in st.session_state:
    st.session_state.documentation = ""
if "quiz" not in st.session_state:
    st.session_state.quiz = []
if "user_answers" not in st.session_state:
    st.session_state.user_answers = {}
if "weak_areas" not in st.session_state:
    st.session_state.weak_areas = []
if "quiz_attempt" not in st.session_state:
    st.session_state.quiz_attempt = 1
if "mastery_achieved" not in st.session_state:
    st.session_state.mastery_achieved = False
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "related_topics" not in st.session_state:
    st.session_state.related_topics = []


# Agent 1: Topic Selector
class TopicSelectorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Topic Selector",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
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


# Agent 2: Video Retriever (Fixed with scrapetube)
class VideoRetrieverAgent:
    @staticmethod
    def fetch_videos(topic: str, limit: int = 10) -> List[Dict]:
        """Fetch top 10 videos and cache them"""
        try:
            videos = []
            video_results = scrapetube.get_search(topic, limit=limit)

            for video in video_results:
                video_id = video.get("videoId")
                if video_id:
                    title = (
                        video.get("title", {})
                        .get("runs", [{}])[0]
                        .get("text", "No title")
                    )

                    # Extract channel name
                    channel_name = "Unknown"
                    if "ownerText" in video and "runs" in video["ownerText"]:
                        channel_name = video["ownerText"]["runs"][0].get(
                            "text", "Unknown"
                        )

                    # Extract views
                    views = "N/A"
                    if (
                        "viewCountText" in video
                        and "simpleText" in video["viewCountText"]
                    ):
                        views = video["viewCountText"]["simpleText"]

                    # Extract duration
                    duration = "N/A"
                    if "lengthText" in video and "simpleText" in video["lengthText"]:
                        duration = video["lengthText"]["simpleText"]

                    videos.append(
                        {
                            "title": title,
                            "link": f"https://www.youtube.com/watch?v={video_id}",
                            "video_id": video_id,
                            "channel": channel_name,
                            "duration": duration,
                            "views": views,
                        }
                    )

                    if len(videos) >= limit:
                        break

            return videos
        except Exception as e:
            st.error(f"Error fetching videos: {e}")
            return []


# Agent 3: Documentation Generator
class DocGeneratorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Documentation Generator",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
            role="Educational Content Creator",
            instructions=[
                "Research and compile comprehensive educational documentation",
                "Structure content with clear sections: Introduction, Key Concepts, Examples, Summary",
                "Use simple language suitable for learners",
                "Include practical examples and real-world applications",
                "Organize information logically with proper headings",
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


# Agent 4: Quiz Generator
class QuizGeneratorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Quiz Generator",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
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


# Agent 5: Evaluator/Coach
class EvaluatorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Learning Coach",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
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


# Agent 6: Q&A Agent
class QAAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Q&A Assistant",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
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


# Agent 7: Related Topics Generator
class RelatedTopicsAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Related Topics Finder",
            model=Gemini(id="gemini-2.5-flash", api_key=api_key),
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
                # Clean up the topic
                topic_text = line.lstrip("0123456789.-* ").strip()
                if topic_text:
                    topics.append(topic_text)

        return topics[:5]


# Main App
def main():
    st.title("Multi Agent Learning Assistant")

    # API Key input
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
        st.warning("Please enter your Gemini API key in the sidebar to continue")
        st.info("Get your API key from: https://aistudio.google.com/app/apikey")
        return

    # Initialize agents
    topic_agent = TopicSelectorAgent(api_key)
    video_agent = VideoRetrieverAgent()
    doc_agent = DocGeneratorAgent(api_key)
    quiz_agent = QuizGeneratorAgent(api_key)
    eval_agent = EvaluatorAgent(api_key)
    qa_agent = QAAgent(api_key)
    related_agent = RelatedTopicsAgent(api_key)

    # Step 1: Topic Input
    if st.session_state.current_step == "topic_input":
        st.header("Select the Topic You want to Learn")
        user_topic = st.text_input(
            "What would you like to learn today?",
            placeholder="e.g., Machine Learning, Python Lists, Photosynthesis",
        )

        if st.button("🚀 Start Learning", type="primary"):
            if user_topic:
                with st.spinner("Analyzing topic..."):
                    topic = asyncio.run(topic_agent.select_topic(user_topic))
                    st.session_state.topic = topic
                    st.session_state.current_step = "fetch_content"
                    st.rerun()
            else:
                st.error("Please enter a topic")

        # Step 2: Fetch Videos and Generate Documentation
    elif st.session_state.current_step == "fetch_content":
        st.header(f"Learning: {st.session_state.topic}")

        with st.spinner("Fetching resources..."):
            # Fetch videos (cache top 10)
            if not st.session_state.videos:
                videos = video_agent.fetch_videos(st.session_state.topic, limit=10)
                st.session_state.videos = videos
                st.session_state.current_video_index = 0

            # Generate documentation
            if not st.session_state.documentation:
                docs = asyncio.run(doc_agent.generate_docs(st.session_state.topic))
                st.session_state.documentation = docs

            st.session_state.current_step = "learning"
            st.rerun()

        # Step 3: Learning Phase (Videos, Docs, Q&A)
    elif st.session_state.current_step == "learning":
        st.header(f"Learning: {st.session_state.topic}")

        # Create tabs
        tab1, tab2 = st.tabs(["Study Material", "Chatbot"])

        # Tab 1: Video and Documentation
        with tab1:
            # Video Section
            if st.session_state.videos:
                st.subheader("Recommended Video")

                current_video = st.session_state.videos[
                    st.session_state.current_video_index
                ]

                # Embed YouTube video
                st.video(current_video["link"])

                # Video details
                st.markdown(f"**{current_video['title']}**")

                st.markdown(f"📺 *{current_video['channel']}*")

                # Next Video Button
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

            # Documentation Section - Fixed markdown rendering
            st.subheader("Study Material")
            # Use unsafe_allow_html=True to ensure proper markdown rendering
            st.markdown(st.session_state.documentation, width="content")

            st.markdown("---")

            # Quiz Button
            if st.button("Take a quiz", type="primary", use_container_width=True):
                st.session_state.current_step = "generate_quiz"
                st.rerun()

        # Tab 2: Q&A
        with tab2:
            st.subheader("Ask Questions About This Topic")

            # Display chat history
            for i, chat in enumerate(st.session_state.chat_history):
                with st.chat_message("user"):
                    st.write(chat["question"])
                with st.chat_message("assistant"):
                    st.markdown(chat["answer"], unsafe_allow_html=False)

            # Question input
            user_question = st.chat_input("Ask a question about the topic...")

            if user_question:
                # Add user question to chat
                with st.chat_message("user"):
                    st.write(user_question)

                # Get answer
                with st.chat_message("assistant"):
                    with st.spinner("Thinking..."):
                        answer = asyncio.run(
                            qa_agent.answer_question(
                                user_question, st.session_state.documentation
                            )
                        )
                        st.markdown(answer, unsafe_allow_html=False)

                # Save to chat history
                st.session_state.chat_history.append(
                    {"question": user_question, "answer": answer}
                )
                st.rerun()

        # Step 4: Generate Quiz
    elif st.session_state.current_step == "generate_quiz":
        with st.spinner("Preparing your quiz..."):
            # Pass weak_areas only if it's not empty, otherwise pass None
            weak_areas_to_pass = (
                st.session_state.weak_areas if st.session_state.weak_areas else None
            )
            quiz = asyncio.run(
                quiz_agent.generate_quiz(
                    st.session_state.documentation, weak_areas_to_pass
                )
            )
            st.session_state.quiz = quiz
            st.session_state.user_answers = {}
            st.session_state.current_step = "take_quiz"
            st.rerun()

        # Step 5: Take Quiz
    elif st.session_state.current_step == "take_quiz":
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
                st.session_state.current_step = "evaluate"
                st.rerun()

        # Step 6: Evaluate
    elif st.session_state.current_step == "evaluate":
        with st.spinner("Evaluating your answers..."):
            results = asyncio.run(
                eval_agent.evaluate(
                    st.session_state.quiz,
                    st.session_state.user_answers,
                    st.session_state.documentation,
                )
            )

            # Generate related topics if mastery achieved
            if results["mastery"] and not st.session_state.related_topics:
                st.session_state.related_topics = asyncio.run(
                    related_agent.get_related_topics(
                        st.session_state.topic, st.session_state.documentation
                    )
                )

            st.header("📊 Quiz Results")

            col1, col2, col3 = st.columns(3)
            col1.metric("Score", f"{results['score']}/{results['total']}")
            col2.metric("Percentage", f"{results['percentage']:.1f}%")
            col3.metric(
                "Status", "✅ Mastery" if results["mastery"] else "Keep Learning"
            )

            st.markdown("---")
            st.subheader("Detailed Feedback")
            st.markdown(results["feedback"], unsafe_allow_html=False)

            # Show correct answers
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
                st.success("🎉 Congratulations! You've mastered this topic!")
                st.balloons()

                # Show related topics
                st.markdown("---")
                st.subheader("Continue Your Learning Journey")
                st.markdown(
                    "Here are some related topics you might want to explore next:"
                )

                for i, related_topic in enumerate(st.session_state.related_topics, 1):
                    col1, col2 = st.columns([4, 1])
                    with col1:
                        st.markdown(f"**{i}.** {related_topic}")
                    with col2:
                        if st.button("Learn", key=f"related_{i}"):
                            # Reset and start learning this topic
                            for key in list(st.session_state.keys()):
                                del st.session_state[key]
                            st.session_state.current_step = "fetch_content"
                            st.session_state.topic = related_topic
                            st.rerun()

                st.markdown("---")
                if st.button("Learn Another Topic", use_container_width=True):
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
            else:
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
                        st.session_state.current_step = "generate_quiz"
                        st.rerun()
                with col2:
                    if st.button("📚 Study Again", use_container_width=True):
                        st.session_state.current_step = "learning"
                        st.rerun()


if __name__ == "__main__":
    main()
