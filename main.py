import asyncio
import openai
# import dotenv
import streamlit as st

# dotenv.load_dotenv()

st.title('Storyspire AI')

topics = ["Guns", "Death", "Politics", "Violence", "Drugs"]
ages = ["5", "6", "7", "8", "9", "10"]
checkbox_values = {}

for i in range(7):
    cols = st.columns(6)
    for j in range(6):
        with cols[j]:
            if i == 0 and j == 0:
                st.text("Age / Topic")
            elif i == 0:
                st.text(topics[j-1])
            elif j == 0:
                st.text(ages[i-1])
            else:
                 checkbox_values[f"checkbox_{i}_{j}"] = st.checkbox("", key=f"checkbox_{i}_{j}")

st.sidebar.title("Settings")
age = st.sidebar.slider("Age Suitability", min_value=5, max_value=10, value=7)
st.sidebar.subheader("Allowed Topics")
# allow_politics = st.sidebar.checkbox('Politics', value=False)
# allow_violence = st.sidebar.checkbox('Violence', value=False)
# allow_mental_health = st.sidebar.checkbox('Mental Health', value=False)

allow_guns = checkbox_values[f'''checkbox_{age-4}_1''']
allow_death = checkbox_values[f'''checkbox_{age-4}_2''']
allow_politics = checkbox_values[f'''checkbox_{age-4}_3''']
allow_violence = checkbox_values[f'''checkbox_{age-4}_4''']
allow_drugs = checkbox_values[f'''checkbox_{age-4}_5''']
print(allow_guns, allow_death, allow_politics, allow_violence, allow_drugs)

GPT_MODEL = "gpt-3.5-turbo"

domain = "story generation"

response_criteria = f"""Assess the presence of any not allowed topics in the content. The not allowed topics are:
{'' if allow_guns else '- Guns'}
{'' if allow_death else '- Death'}
{'' if allow_politics else '- Politics'}
{'' if allow_violence else '- Extreme violence'}
{'' if allow_drugs else '- Drugs'}
"""

response_safety_steps = """
1. Read the content and the criteria carefully.
2. Assess whether any not allowed topics are contained in the content.
3. Assign a score from 1 to 5, with 1 being content doesn't contain any not allowed topics, and 5 being the content definitely contains topics that are not allowed.
"""

moderation_system_prompt = """
You are a moderation assistant. Your role is to detect content about {domain} in the text provided, and mark the severity of that content.

## {domain}

### Criteria

{scoring_criteria}

### Instructions

{scoring_steps}

### Content

{content}

### Evaluation (score only!)
"""

async def get_chat_response(user_request):
    print("Getting LLM response")
    messages = [
        {"role": "system", "content": "You write stories about the topic that is requested. Your response begins immediately with the story and ends with the story, i.e. there should be no other comentary such as 'Ok, here is a story' or 'I hope you like it' or 'I hope this helps'"},
        {"role": "user", "content": user_request },
    ]
    response = openai.chat.completions.create(
        model=GPT_MODEL, messages=messages, temperature=0.5
    )
    print("Got LLM response")

    return response.choices[0].message.content


async def topical_guardrail(user_request):
    print("Checking topical guardrail")
    messages = [
        {
            "role": "system",
            "content": f'''Your role is to assess whether the user question is allowed or not. The topics not allowed are:
            {'' if allow_guns else ' - Guns'}
            {'' if allow_death else ' - Death'}
            {'' if allow_politics else ' - Politics'}
            {'' if allow_violence else ' - Extreme violence'}
            {'' if allow_drugs else ' - Drugs'}
            

            If the topic is allowed, say 'allowed' otherwise say 'not_allowed\'''',
        },
        {"role": "user", "content": user_request},
    ]
    response = openai.chat.completions.create(
        model=GPT_MODEL, messages=messages, temperature=0
    )

    print("Got guardrail response")
    return response.choices[0].message.content


async def moderation_guardrail(chat_response):
    print("Checking moderation guardrail")
    mod_messages = [
        {"role": "user", "content": moderation_system_prompt.format(
            domain=domain,
            scoring_criteria=response_criteria,
            scoring_steps=response_safety_steps,
            content=chat_response
        )},
    ]
    response = openai.chat.completions.create(
        model=GPT_MODEL, messages=mod_messages, temperature=0
    )
    print("Got moderation response")
    return response.choices[0].message.content
    

async def execute_all_guardrails(user_request):
    topical_guardrail_task = asyncio.create_task(topical_guardrail(user_request))
    chat_task = asyncio.create_task(get_chat_response(user_request))

    while True:
        done, _ = await asyncio.wait(
            [topical_guardrail_task, chat_task], return_when=asyncio.FIRST_COMPLETED
        )
        if topical_guardrail_task in done:
            guardrail_response = topical_guardrail_task.result()
            if guardrail_response == "not_allowed":
                chat_task.cancel()
                print("Topical guardrail triggered")
                return "Sorry, I cannot write about that."
            elif chat_task in done:
                chat_response = chat_task.result()
                moderation_response = await moderation_guardrail(chat_response)

                if int(moderation_response) >= 3:
                    print(f"Moderation guardrail flagged with a score of {int(moderation_response)}")
                    return "Sorry, I don't feel comfortable writing about that."

                else:
                    print('Passed moderation with score of', int(moderation_response))
                    return chat_response
        else:
            await asyncio.sleep(0.1)


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["message"])

if prompt := st.chat_input("Ask your question"):
    st.session_state.messages.append({"role": "USER", "message": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Generating response..."):
            message_placeholder = st.empty()
            full_response = asyncio.run(execute_all_guardrails(prompt))
            message_placeholder.markdown(full_response)
    st.session_state.messages.append({"role": "CHATBOT", "message": full_response})
