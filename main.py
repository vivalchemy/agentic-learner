import streamlit as st
import asyncio
from typing import List, Dict
import json
from agno.agent import Agent
from agno.models.google import Gemini
from youtubesearchpython import VideosSearch
import os

# Set page config
st.set_page_config(
    page_title="AI Learning Assistant",
    page_icon="🎓",
    layout="wide"
)

# Initialize session state
if 'current_step' not in st.session_state:
    st.session_state.current_step = 'topic_input'
if 'topic' not in st.session_state:
    st.session_state.topic = ''
if 'videos' not in st.session_state:
    st.session_state.videos = []
if 'documentation' not in st.session_state:
    st.session_state.documentation = ''
if 'quiz' not in st.session_state:
    st.session_state.quiz = []
if 'user_answers' not in st.session_state:
    st.session_state.user_answers = {}
if 'weak_areas' not in st.session_state:
    st.session_state.weak_areas = []
if 'quiz_attempt' not in st.session_state:
    st.session_state.quiz_attempt = 1
if 'mastery_achieved' not in st.session_state:
    st.session_state.mastery_achieved = False

# Agent 1: Topic Selector
class TopicSelectorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Topic Selector",
            model=Gemini(
                id="gemini-2.0-flash-exp",
                api_key=api_key
            ),
            role="Topic Selection Expert",
            instructions=[
                "Analyze user input and extract or refine the learning topic",
                "Ensure the topic is clear, specific, and suitable for learning",
                "If topic is vague, make it more specific and educational"
            ],
            markdown=True
        )
    
    async def select_topic(self, user_input: str) -> str:
        response = await self.agent.arun(
            f"Extract and refine a clear learning topic from: '{user_input}'. "
            f"Return ONLY the topic name, nothing else."
        )
        return response.content.strip()

# Agent 2: Video Retriever
class VideoRetrieverAgent:
    @staticmethod
    def fetch_videos(topic: str, limit: int = 5) -> List[Dict]:
        try:
            videos_search = VideosSearch(topic, limit=limit)
            results = videos_search.result()
            
            videos = []
            for video in results.get('result', []):
                videos.append({
                    'title': video.get('title'),
                    'link': video.get('link'),
                    'channel': video.get('channel', {}).get('name'),
                    'duration': video.get('duration'),
                    'views': video.get('viewCount', {}).get('text')
                })
            return videos
        except Exception as e:
            st.error(f"Error fetching videos: {e}")
            return []

# Agent 3: Documentation Generator
class DocGeneratorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Documentation Generator",
            model=Gemini(
                id="gemini-2.0-flash-exp",
                api_key=api_key
            ),
            role="Educational Content Creator",
            instructions=[
                "Research and compile comprehensive educational documentation",
                "Structure content with clear sections: Introduction, Key Concepts, Examples, Summary",
                "Use simple language suitable for learners",
                "Include practical examples and real-world applications",
                "Organize information logically with proper headings"
            ],
            markdown=True
        )
    
    async def generate_docs(self, topic: str) -> str:
        response = await self.agent.arun(
            f"Create comprehensive educational documentation about '{topic}'. "
            f"Include: 1) Introduction, 2) Core Concepts (with definitions), "
            f"3) Practical Examples, 4) Key Takeaways. "
            f"Make it detailed but easy to understand."
        )
        return response.content

# Agent 4: Quiz Generator
class QuizGeneratorAgent:
    def __init__(self, api_key: str):
        self.agent = Agent(
            name="Quiz Generator",
            model=Gemini(
                id="gemini-2.0-flash-exp",
                api_key=api_key
            ),
            role="Assessment Creator",
            instructions=[
                "Generate multiple-choice questions based on documentation",
                "Create 5 questions covering different aspects of the topic",
                "Each question should have 4 options with only one correct answer",
                "Include questions of varying difficulty",
                "Format as JSON array"
            ],
            markdown=False
        )
    
    async def generate_quiz(self, documentation: str, weak_areas: List[str] = None) -> List[Dict]:
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
            # Extract JSON from response
            content = response.content.strip()
            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
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
            model=Gemini(
                id="gemini-2.0-flash-exp",
                api_key=api_key
            ),
            role="Learning Assessment Expert",
            instructions=[
                "Evaluate student answers and identify knowledge gaps",
                "Determine which concepts need more focus",
                "Decide if student has achieved mastery (80%+ correct)",
                "Provide constructive feedback",
                "Be encouraging but honest about areas needing improvement"
            ],
            markdown=True
        )
    
    async def evaluate(self, quiz: List[Dict], answers: Dict, documentation: str) -> Dict:
        # Calculate score
        correct_count = 0
        total = len(quiz)
        weak_topics = []
        
        for i, q in enumerate(quiz):
            user_answer = answers.get(i, -1)
            if user_answer == q['correct']:
                correct_count += 1
            else:
                weak_topics.append(q['question'])
        
        score_percent = (correct_count / total * 100) if total > 0 else 0
        mastery = score_percent >= 80
        
        # Get AI feedback
        feedback_prompt = (
            f"A student scored {correct_count}/{total} ({score_percent:.1f}%) on a quiz about the topic. "
            f"Questions they got wrong: {weak_topics if weak_topics else 'None'}. "
            f"Documentation: {documentation[:500]}... "
            f"Provide: 1) Encouraging feedback, 2) Specific areas to review, 3) Whether they achieved mastery."
        )
        
        response = await self.agent.arun(feedback_prompt)
        
        return {
            'score': correct_count,
            'total': total,
            'percentage': score_percent,
            'mastery': mastery,
            'feedback': response.content,
            'weak_areas': weak_topics
        }

# Main App
def main():
    st.title("🎓 AI-Powered Learning Assistant")
    st.markdown("*Learn any topic with personalized videos, documentation, and adaptive quizzes*")
    
    # API Key input
    api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")
    
    if not api_key:
        st.warning("⚠️ Please enter your Gemini API key in the sidebar to continue")
        st.info("Get your API key from: https://aistudio.google.com/app/apikey")
        return
    
    # Initialize agents
    topic_agent = TopicSelectorAgent(api_key)
    video_agent = VideoRetrieverAgent()
    doc_agent = DocGeneratorAgent(api_key)
    quiz_agent = QuizGeneratorAgent(api_key)
    eval_agent = EvaluatorAgent(api_key)
    
    # Step 1: Topic Input
    if st.session_state.current_step == 'topic_input':
        st.header("Step 1: Choose Your Learning Topic")
        user_topic = st.text_input("What would you like to learn today?", 
                                   placeholder="e.g., Machine Learning, Python Lists, Photosynthesis")
        
        if st.button("🚀 Start Learning", type="primary"):
            if user_topic:
                with st.spinner("Analyzing topic..."):
                    topic = asyncio.run(topic_agent.select_topic(user_topic))
                    st.session_state.topic = topic
                    st.session_state.current_step = 'fetch_videos'
                    st.rerun()
            else:
                st.error("Please enter a topic")
    
    # Step 2: Fetch Videos
    elif st.session_state.current_step == 'fetch_videos':
        st.header(f"📚 Learning: {st.session_state.topic}")
        
        with st.spinner("Finding best YouTube videos..."):
            videos = video_agent.fetch_videos(st.session_state.topic)
            st.session_state.videos = videos
            st.session_state.current_step = 'show_videos'
            st.rerun()
    
    # Step 3: Show Videos and Generate Docs
    elif st.session_state.current_step == 'show_videos':
        st.header(f"📚 Learning: {st.session_state.topic}")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📺 Recommended Videos")
            for video in st.session_state.videos:
                with st.expander(f"🎥 {video['title'][:60]}..."):
                    st.markdown(f"**Channel:** {video['channel']}")
                    st.markdown(f"**Duration:** {video['duration']}")
                    st.markdown(f"**Views:** {video['views']}")
                    st.markdown(f"[Watch Video]({video['link']})")
        
        with col2:
            if not st.session_state.documentation:
                with st.spinner("Generating comprehensive documentation..."):
                    docs = asyncio.run(doc_agent.generate_docs(st.session_state.topic))
                    st.session_state.documentation = docs
                    st.rerun()
            else:
                st.subheader("📖 Study Material")
                st.markdown(st.session_state.documentation)
        
        if st.session_state.documentation:
            if st.button("✅ I've Studied - Take Quiz", type="primary"):
                st.session_state.current_step = 'generate_quiz'
                st.rerun()
    
    # Step 4: Generate Quiz
    elif st.session_state.current_step == 'generate_quiz':
        with st.spinner("Preparing your quiz..."):
            quiz = asyncio.run(quiz_agent.generate_quiz(
                st.session_state.documentation,
                st.session_state.weak_areas if st.session_state.weak_areas else None
            ))
            st.session_state.quiz = quiz
            st.session_state.user_answers = {}
            st.session_state.current_step = 'take_quiz'
            st.rerun()
    
    # Step 5: Take Quiz
    elif st.session_state.current_step == 'take_quiz':
        st.header(f"📝 Quiz - Attempt #{st.session_state.quiz_attempt}")
        st.markdown(f"**Topic:** {st.session_state.topic}")
        
        with st.form("quiz_form"):
            for i, q in enumerate(st.session_state.quiz):
                st.markdown(f"**Question {i+1}:** {q['question']}")
                answer = st.radio(
                    f"Select your answer:",
                    options=range(len(q['options'])),
                    format_func=lambda x, opts=q['options']: opts[x],
                    key=f"q_{i}"
                )
                st.session_state.user_answers[i] = answer
                st.markdown("---")
            
            submitted = st.form_submit_button("Submit Quiz", type="primary")
            
            if submitted:
                st.session_state.current_step = 'evaluate'
                st.rerun()
    
    # Step 6: Evaluate
    elif st.session_state.current_step == 'evaluate':
        with st.spinner("Evaluating your answers..."):
            results = asyncio.run(eval_agent.evaluate(
                st.session_state.quiz,
                st.session_state.user_answers,
                st.session_state.documentation
            ))
            
            st.header("📊 Quiz Results")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Score", f"{results['score']}/{results['total']}")
            col2.metric("Percentage", f"{results['percentage']:.1f}%")
            col3.metric("Status", "✅ Mastery" if results['mastery'] else "📚 Keep Learning")
            
            st.markdown("---")
            st.subheader("Detailed Feedback")
            st.markdown(results['feedback'])
            
            # Show correct answers
            st.markdown("---")
            st.subheader("Answer Review")
            for i, q in enumerate(st.session_state.quiz):
                user_ans = st.session_state.user_answers.get(i, -1)
                correct = user_ans == q['correct']
                
                with st.expander(f"{'✅' if correct else '❌'} Question {i+1}: {q['question'][:50]}..."):
                    st.markdown(f"**Your answer:** {q['options'][user_ans] if user_ans >= 0 else 'Not answered'}")
                    st.markdown(f"**Correct answer:** {q['options'][q['correct']]}")
                    st.markdown(f"**Explanation:** {q.get('explanation', 'N/A')}")
            
            if results['mastery']:
                st.success("🎉 Congratulations! You've mastered this topic!")
                st.balloons()
                if st.button("Learn Another Topic"):
                    # Reset everything
                    for key in list(st.session_state.keys()):
                        del st.session_state[key]
                    st.rerun()
            else:
                st.warning("📚 You need more practice. Let's focus on your weak areas!")
                st.session_state.weak_areas = results['weak_areas'][:3]  # Top 3 weak areas
                st.session_state.quiz_attempt += 1
                
                if st.button("🔄 Retake Quiz (Focused on Weak Areas)", type="primary"):
                    st.session_state.current_step = 'generate_quiz'
                    st.rerun()

if __name__ == "__main__":
    main()

