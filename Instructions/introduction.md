PydanticAI is a Python agent framework designed to make it less painful to build production grade applications with Generative AI.

PydanticAI is a Python Agent Framework designed to make it less painful to build production grade applications with Generative AI.

FastAPI revolutionized web development by offering an innovative and ergonomic design, built on the foundation of Pydantic.

Similarly, virtually every agent framework and LLM library in Python uses Pydantic, yet when we began to use LLMs in Pydantic Logfire, we couldn't find anything that gave us the same feeling.

We built PydanticAI with one simple aim: to bring that FastAPI feeling to GenAI app development.

Why use PydanticAI
Built by the Pydantic Team: Built by the team behind Pydantic (the validation layer of the OpenAI SDK, the Anthropic SDK, LangChain, LlamaIndex, AutoGPT, Transformers, CrewAI, Instructor and many more).

Model-agnostic: Supports OpenAI, Anthropic, Gemini, Deepseek, Ollama, Groq, Cohere, and Mistral, and there is a simple interface to implement support for other models.

Pydantic Logfire Integration: Seamlessly integrates with Pydantic Logfire for real-time debugging, performance monitoring, and behavior tracking of your LLM-powered applications.

Type-safe: Designed to make type checking as powerful and informative as possible for you.

Python-centric Design: Leverages Python's familiar control flow and agent composition to build your AI-driven projects, making it easy to apply standard Python best practices you'd use in any other (non-AI) project.

Structured Responses: Harnesses the power of Pydantic to validate and structure model outputs, ensuring responses are consistent across runs.

Dependency Injection System: Offers an optional dependency injection system to provide data and services to your agent's system prompts, tools and result validators. This is useful for testing and eval-driven iterative development.

Streamed Responses: Provides the ability to stream LLM outputs continuously, with immediate validation, ensuring rapid and accurate results.

Graph Support: Pydantic Graph provides a powerful way to define graphs using typing hints, this is useful in complex applications where standard control flow can degrade to spaghetti code.

In Beta

PydanticAI is in early beta, the API is still subject to change and there's a lot more to do. Feedback is very welcome!

Hello World Example
Here's a minimal example of PydanticAI:

hello_world.py

from pydantic_ai import Agent

agent = Agent(  
    'google-gla:gemini-1.5-flash',
    system_prompt='Be concise, reply with one sentence.',  
)

result = agent.run_sync('Where does "hello world" come from?')  
print(result.data)
"""
The first known use of "hello, world" was in a 1974 textbook about the C programming language.
"""
(This example is complete, it can be run "as is")

The exchange should be very short: PydanticAI will send the system prompt and the user query to the LLM, the model will return a text response.

Not very interesting yet, but we can easily add "tools", dynamic system prompts, and structured responses to build more powerful agents.

Tools & Dependency Injection Example
Here is a concise example using PydanticAI to build a support agent for a bank:

bank_support.py

from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from bank_database import DatabaseConn


@dataclass
class SupportDependencies:  
    customer_id: int
    db: DatabaseConn  


class SupportResult(BaseModel):  
    support_advice: str = Field(description='Advice returned to the customer')
    block_card: bool = Field(description="Whether to block the customer's card")
    risk: int = Field(description='Risk level of query', ge=0, le=10)


support_agent = Agent(  
    'openai:gpt-4o',  
    deps_type=SupportDependencies,
    result_type=SupportResult,  
    system_prompt=(  
        'You are a support agent in our bank, give the '
        'customer support and judge the risk level of their query.'
    ),
)


@support_agent.system_prompt  
async def add_customer_name(ctx: RunContext[SupportDependencies]) -> str:
    customer_name = await ctx.deps.db.customer_name(id=ctx.deps.customer_id)
    return f"The customer's name is {customer_name!r}"


@support_agent.tool  
async def customer_balance(
    ctx: RunContext[SupportDependencies], include_pending: bool
) -> float:
    """Returns the customer's current account balance."""  
    return await ctx.deps.db.customer_balance(
        id=ctx.deps.customer_id,
        include_pending=include_pending,
    )


...  


async def main():
    deps = SupportDependencies(customer_id=123, db=DatabaseConn())
    result = await support_agent.run('What is my balance?', deps=deps)  
    print(result.data)  
    """
    support_advice='Hello John, your current account balance, including pending transactions, is $123.45.' block_card=False risk=1
    """

    result = await support_agent.run('I just lost my card!', deps=deps)
    print(result.data)
    """
    support_advice="I'm sorry to hear that, John. We are temporarily blocking your card to prevent unauthorized transactions." block_card=True risk=8
    """
Complete bank_support.py example

The code included here is incomplete for the sake of brevity (the definition of DatabaseConn is missing); you can find the complete bank_support.py example here.

Instrumentation with Pydantic Logfire
To understand the flow of the above runs, we can watch the agent in action using Pydantic Logfire.

To do this, we need to set up logfire, and add the following to our code:

bank_support_with_logfire.py

...
from bank_database import DatabaseConn

import logfire
logfire.configure()  
logfire.instrument_asyncpg()  
...
That's enough to get the following view of your agent in action:


See Monitoring and Performance to learn more.