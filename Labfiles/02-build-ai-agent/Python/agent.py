import os
from pathlib import Path
from azure.identity import DefaultAzureCredential
from azure.ai.agents import AgentsClient
from azure.ai.agents.models import FilePurpose, CodeInterpreterTool, ListSortOrder, MessageRole

def main():
    # Replace these with your actual values
    project_endpoint = "https://chrysantheumagent-resource.services.ai.azure.com/api/projects/chrysantheumagent"
    file_path = "./data/sample.csv"

    # Connect to the Agent client
    agent_client = AgentsClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(
            exclude_environment_credential=True,
            exclude_managed_identity_credential=True
        )
    )

    with agent_client:
        # Upload the data file
        file = agent_client.files.upload_and_poll(
            file_path=file_path,
            purpose=FilePurpose.AGENTS
        )
        print(f"✅ Uploaded {file.filename}")

        # Create the tool
        code_interpreter = CodeInterpreterTool(file_ids=[file.id])

        # Create the agent
        agent = agent_client.create_agent(
            model="gpt-4o",
            name="data-agent",
            instructions="You are an AI agent that analyzes the data in the file that has been uploaded. "
                         "If the user requests a chart, create it and save it as a .png file.",
            tools=code_interpreter.definitions,
            tool_resources=code_interpreter.resources,
        )
        print(f"🤖 Using agent: {agent.name}")

        # Create a thread
        thread = agent_client.threads.create()

        # Prompt loop
        while True:
            user_prompt = input("💬 Enter a prompt (or type 'quit' to exit): ")
            if user_prompt.lower() == "quit":
                break
            if not user_prompt.strip():
                print("⚠️ Please enter a prompt.")
                continue

            # Send message to agent
            message = agent_client.messages.create(
                thread_id=thread.id,
                role="user",
                content=user_prompt
            )

            # Run the agent
            run = agent_client.runs.create_and_process(
                thread_id=thread.id,
                agent_id=agent.id
            )

            if run.status == "failed":
                print(f"❌ Run failed: {run.last_error}")
                continue

            # Get the agent's response
            last_msg = agent_client.messages.get_last_message_text_by_role(
                thread_id=thread.id,
                role=MessageRole.AGENT,
            )
            if last_msg:
                print(f"🤖 Agent: {last_msg.text.value}")

        # Print full conversation
        print("\n📜 Conversation Log:\n")
        messages = agent_client.messages.list(
            thread_id=thread.id,
            order=ListSortOrder.ASCENDING
        )
        for message in messages:
            if message.text_messages:
                last_msg = message.text_messages[-1]
                print(f"{message.role}: {last_msg.text.value}\n")

        # Save generated image files (charts)
        for msg in messages:
            for img in msg.image_contents:
                file_id = img.image_file.file_id
                file_name = f"{file_id}_image_file.png"
                agent_client.files.save(file_id=file_id, file_name=file_name)
                print(f"🖼️ Saved image file to: {Path.cwd() / file_name}")

        # Clean up
        agent_client.agents.delete(agent.id)
        print("🧹 Agent deleted.")

# ✅ Entry point
if __name__ == '__main__':
    main()
