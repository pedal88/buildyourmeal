import os
from jinja2 import Environment, FileSystemLoader

class PromptManager:
    def __init__(self, prompts_dir=None):
        if not prompts_dir:
            # Default to data/prompts relative to project root
            # Assuming this file is in utils/ and root is one level up
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            prompts_dir = os.path.join(root_dir, 'data', 'prompts')
        
        self.prompts_dir = prompts_dir
        self.env = Environment(loader=FileSystemLoader(self.prompts_dir))

    def load_prompt(self, filename, **kwargs):
        """
        Loads a Jinja2 template by filename and renders it with the provided kwargs.
        """
        try:
            template = self.env.get_template(filename)
            return template.render(**kwargs)
        except Exception as e:
            # Fallback or re-raise with context
            print(f"Error rendering prompt {filename}: {e}")
            raise e

# specific singleton instance if needed, or just class
prompt_manager = PromptManager()

def load_prompt(filename, **kwargs):
    """
    Convenience wrapper for the singleton instance.
    """
    return prompt_manager.load_prompt(filename, **kwargs)
