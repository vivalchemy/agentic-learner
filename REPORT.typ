#import "@preview/fletcher:0.5.8" as fletcher: diagram, node, edge
#set rect(inset: 4pt)
#show link: set text(fill: blue)
#show link: underline

= Agentic Learner

=== *An Adaptive Educational System Using Specialized AI Agents*

=== Members
- 9914 Vivian Ludrick
- 9899 Cyrus Gomes
- Github Repository - https://github.com/vivalchemy/agentic-learner

== Abstract
This system implements a multi-agent architecture for personalized
learning, utilizing seven specialized AI agents powered by Google’s
Gemini models. The agents collaborate through a state machine workflow
to provide topic selection, content curation, documentation generation,
quiz assessment, Q&A support, and adaptive learning path
recommendations. The system achieves personalized education by
identifying knowledge gaps and dynamically adjusting content based on
learner performance.

== Introduction
Traditional learning platforms lack adaptability and personalized
assessment. This multi-agent system addresses these limitations by
distributing educational tasks across specialized agents, each optimized
for specific functions. The agents work collaboratively to create a
complete learning cycle: from topic refinement and content generation to
assessment and mastery verification. Built with Streamlit and the Agno
framework, the system leverages Gemini’s language models to provide
intelligent, context-aware educational support.

== Implementation Steps
=== Technology Stack
==== Core Framework & UI
- *Streamlit*: Web application framework providing the
  interactive user interface with built-in state management, forms,
  tabs, and real-time updates
- *Python 3.12*: Primary programming language with `asyncio` for
  asynchronous agent operations

==== AI/ML Infrastructure
- *Agno Framework*: Agent orchestration library providing the
  Agent class for creating specialized AI agents with role-based
  instructions
- *Google Gemini Models*:
  - `gemini-2.5-flash`: Fast model used for all agents (topic selection,
    documentation, quiz generation, evaluation, Q&A, related topics)
  - `gemini-2.5-pro`: Available as pro option for enhanced reasoning
- *Async Processing*: Python’s asyncio for concurrent API calls
  and non-blocking agent operations

==== Content Retrieval
- *Scrapetube*: YouTube video scraping library for fetching
  educational videos without official API requirements
- *DocGenerator Agent*: Generate a through documentation for
  that topic

=== Architecture Components
==== 1. Agent Manager (AgentManager)
Centralized orchestrator that initializes and maintains all _seven
specialized agents_:

+ #underline()[Topic Selector Agent]: Analyzes user input to extract and refine
  learning topics into clear, specific, and educationally appropriate
  subjects.
+ #underline()[Video Retriever Agent]: Fetches relevant YouTube educational videos
  using the scrapetube library, providing curated multimedia learning
  resources.
+ #underline()[Documentation Generator Agent]: Creates comprehensive educational
  documentation with structured sections: introduction, key concepts,
  practical examples, and summaries tailored to the learning topic.
+ #underline()[Quiz Generator Agent]: Produces multiple-choice assessments with five
  questions covering various difficulty levels and topic aspects. Can
  focus on identified weak areas for adaptive learning.
+ #underline()[Evaluator Agent]: Analyzes quiz performance to calculate scores,
  identify knowledge gaps, determine mastery achievement (≥80%), and
  provide constructive feedback on areas needing improvement.
+ #underline()[Q&A Agent]: Provides interactive question-answering capabilities,
  offering clear explanations based on the generated documentation to
  support learner queries.
+ #underline()[Related Topics Agent]: Suggests five complementary learning topics when
  mastery is achieved, creating continuous learning pathways and
  building on acquired knowledge.

Each agent follows consistent architecture: - Gemini model
initialization with specific role and instructions - Markdown formatting
(enabled/disabled based on output type) - Async `arun()` method for LLM
inference - Error handling and fallback responses

==== 2. State Machine (LearningStateMachine)
Implements finite state machine pattern with six states: -
`TOPIC_INPUT`: User topic entry - `FETCH_CONTENT`: Resource retrieval -
`LEARNING`: Study material presentation with video carousel and chatbot
\- `GENERATE_QUIZ`: Quiz creation with weak area focusing - `TAKE_QUIZ`:
Assessment interface with radio button selections - `EVALUATE`:
Performance analysis and feedback generation

==== 3. State Transition Diagram
#diagram(
  node-stroke: 0.5pt,
  node-fill: blue.lighten(50%),
  spacing: (3em, 2em),
  edge-stroke: 1pt,
  
  // Start node
  node((0, 0), [●], stroke: none, fill: black, radius: 8pt, name: <start>),
  edge("-|>"),
  
  // Topic Input state
  node((0, 1), [
    *Topic Input*\
    #text(size: 9pt)[User enters learning topic]
  ], corner-radius: 5pt, name: <topic>),
  edge("-|>"),
  
  // Fetch Content state
  node((1,1), [
    *Fetch Content*
  ], corner-radius: 5pt, name: <fetch>),
  edge("-|>"),
  
  // Learning state
  node((2, 1), [
    *Learning*
  ], corner-radius: 5pt, name: <learn>),
  
  // Self-loop for chatbot
  edge(<learn>, <learn>, "-|>", [Ask questions], bend: 130deg, label-side: left),
  
  edge(<learn>,<quiz>, "-|>"),
  
  // Generate Quiz state
  node((2, 2), [
    *Generate Quiz*
  ], corner-radius: 5pt, name: <quiz>),
  edge("-|>"),
  
  // Take Quiz state
  node((2, 3), [
    *Take Quiz*
  ], corner-radius: 5pt, name: <take>),
  edge("-|>"),
  
  // Evaluate state
  node((1, 3), [
    *Evaluate*
    #text(size: 9pt)[Check results & feedback]
  ], corner-radius: 5pt, name: <eval>),
  
  // Return paths
  edge(<eval>, <quiz>, "-|>", [Retake], label-side: center),
  edge(<eval>, <learn>, "-|>"),
  edge(<eval>, <topic>, "-|>", [Learn another topic], label-side: left),
  edge(<eval>, <fetch>, "-|>", [Select related topic], label-side: center),
  edge(<eval>, <end>, "-|>", [Quit]),
  edge(<start>, <topic>, "-|>", [Start]),
  
  node((1, 4), [●], stroke: 2pt, fill: white, radius: 8pt, name: <end>),
)

==== 4. Adaptive Learning Mechanism
*Feedback Loop:* 1. Evaluator identifies incorrect answers 2.
Weak areas extracted from failed questions 3. Quiz Generator receives
weak areas as context 4. Regenerated quiz focuses 60%+ questions on weak
concepts 5. Attempt counter increments for progress tracking

*Mastery Criteria:* - Score ≥ 80% triggers mastery state -
Related Topics Agent activated only after mastery - Balloon animation
and congratulatory messaging

== Conclusion
This multi-agent architecture demonstrates effective task decomposition
in educational systems. By assigning specialized roles to distinct
agents, the system achieves adaptive, personalized learning experiences
that respond to individual performance. The evaluator-driven feedback
loop and weak-area focusing mechanism enable iterative improvement until
mastery. The modular design allows easy extension with additional agents
for enhanced functionality, making it a scalable framework for
AI-powered education.

== Screenshots
#image("./assets/01Oct25_21h54m02s.png", width: 35em)
#image("./assets/01Oct25_21h55m47s.png", width: 35em)
#image("./assets/01Oct25_21h55m50s.png", width: 35em)
#image("./assets/01Oct25_21h55m53s.png", width: 35em)
#image("./assets/01Oct25_21h56m39s.png", width: 35em)
#image("./assets/01Oct25_21h57m59s.png", width: 35em)
#image("./assets/01Oct25_21h58m47s.png", width: 35em)
#image("./assets/01Oct25_21h59m11s.png", width: 35em)
#image("./assets/01Oct25_21h59m16s.png", width: 35em)
#image("./assets/01Oct25_21h59m18s.png", width: 35em)
#image("./assets/01Oct25_21h59m34s.png", width: 35em)
#image("./assets/01Oct25_22h00m55s.png", width: 35em)
#image("./assets/01Oct25_22h01m00s.png", width: 35em)
#image("./assets/01Oct25_22h01m05s.png", width: 35em)

