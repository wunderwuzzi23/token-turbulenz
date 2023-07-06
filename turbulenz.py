import openai
import time
import logging
import os
import argparse
from termcolor import colored
import yaml
import json

# Configure logging
logging.basicConfig(filename='fuzzer.log', level=logging.INFO, format='%(asctime)s %(message)s')

# Set the openai API key
openai.api_key = os.environ['OPENAI_API_KEY']

def read_yaml_template(file_path):
    """
    Load a YAML template from the given file path.
    """
    with open(file_path, 'r') as f:
        data = yaml.safe_load(f)
    return data

def test_token(token, model, temperature, verbose, template_messages, injection_success_string, injection_instruction, max_retries):
    """
    Test a given token using the OpenAI API, and return whether the test was successful.
    """

    messages = []
    # Build message array
    for message in template_messages:

        # Insert the token into the prompt and append the injection instructions
        test_case = f"{token}{injection_instruction}"
        # print(message)
        message["content"] = str(message["content"]).format(test_case)

        messages.append(message)

    if verbose:
        logging.info(f"Messages: {messages}")

    retries = 0

    while retries < max_retries:
        try:

            response=""
            if openai.api_type == "azure":
                response = openai.ChatCompletion.create(
                    deployment_id=model,
                    messages=messages,
                    max_tokens=1000,
                    temperature=temperature
                )
            else:
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    max_tokens=1000,
                    temperature=temperature
                )
            break
        except Exception as e:
            print(f"Error: {e}. Retry {retries}...")
            retries += 1
            time.sleep(3)

        if retries == max_retries:
            logging.error(f"Failed to test token '{token}' after {max_retries} retries")
            return False

    #print this in JSON in future
    logging.info(f"Test Case: {test_case} | Response: {response.choices[0].message.content}") 
    data = {
        "token": token,
        "request": messages,
        "temperature": temperature,
        "response": response
    }

    with open("results.json", "a") as outfile:
        json.dump(data, outfile)
        outfile.write("\n")

    return injection_success_string in response.choices[0].message.content


def print_banner(model, temperature, count, prompt_template, injection_instruction, injection_success_string):
    """
    Print the banner and the current test setup.
    """
    print("********************************")
    print("*** Token Turbulenz - Fuzzer ***")
    print("********************************\n")
    print(f"Model:       {model}")
    print(f"Temperature: {str(temperature)}")
    print(f"Count:       {str(count)}\n")
    print("Prompt Template:")
    print(colored(prompt_template, "green"))
    print("\nInstruction:")
    print(colored(injection_instruction, "red"))
    print("\nSuccess Case:")
    print(colored(injection_success_string,"yellow"))
    print()


def main(args):
    data = read_yaml_template(args.template)["template"][0]
    print_banner(args.model, args.temperature, args.count, data["messages"], data["payload"], data["success"])

    # Load the tokens from the file
    with open('tokens.list', 'r') as f:
        tokens = f.read().splitlines()

    print("Testing in progress..")

    for i, token in enumerate(tokens[args.start_index:], start=args.start_index):
        
        print("Test #{:>6} | Token: {:<12} | Result: ".format(i, token), end="", flush=True)
        #logging.info(f"Test #{i:>6} | Token: {token:<12} | Result: ")

        test_success = test_token(token, args.model, args.temperature, args.verbose, data["messages"], 
                                  data["success"], data["payload"], args.max_retries)

        result_color = "yellow" if test_success else "red"
        result_text = "Success" if test_success else "Failed"
        print(colored(result_text, result_color))
        #logging.info(colored(result_text, result_color))

        time.sleep(1)
        # Break the loop if the count limit has been reached
        if args.count and i >= args.start_index + args.count-1:
            break 


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Token Turbulenz")

    parser.add_argument('--template', type=str, default="./templates/default.yaml", help='Path to YAML template file')
    parser.add_argument('--model', type=str, default="gpt-3.5-turbo", help='Model to use for testing, if Azure this is the Deployment ID')
    parser.add_argument('--max_retries', type=int, default=3, help='Maximum retries API is busy')
    parser.add_argument('--temperature', type=float, default=0.2, help='Temperature setting for chat completion call')
    parser.add_argument('--verbose', type=bool, default=False, help='Print prompts')
    parser.add_argument('--start_index', type=int, default=0, help='Token start index')
    parser.add_argument('--count', type=int, default=10, help='How many tokens to test, starting from start index.')
    parser.add_argument('--azure_base_api', type=str, default="", help='If you want to use Azure OpenAI, set the endpoint')
    #parser.add_argument('--azure_deployment_id', type=str, default="", help='Name of the Azure OAI deployment')
    parser.add_argument('--azure_version', type=str, default="2023-03-15-preview", help='Azure OpenAI API version')
    
    args = parser.parse_args()

    #Are we using Azure OpenAI?
    if args.azure_base_api !="":
        print("args.azure_base_api")
        print("args.azure_version")
        openai.api_type = "azure"
        openai.api_base = args.azure_base_api
        openai.api_version = args.azure_version

    main(args)
