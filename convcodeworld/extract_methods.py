import ast

class MethodExtractor(ast.NodeVisitor):
    def __init__(self):
        self.methods = []

    def visit_FunctionDef(self, node):
        self.methods.append(node.name)
        self.generic_visit(node)

def extract_methods_from_class(class_definition):
    tree = ast.parse(class_definition)
    method_extractor = MethodExtractor()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            method_extractor.visit(node)
    return method_extractor.methods


if __name__ == '__main__':
    # Example usage
    class_definition = """
class ExampleClass:
    def method_one(self):
        pass

    def method_two(self, arg):
        pass

    def method_three(self, arg1, arg2):
        pass
"""

    methods = extract_methods_from_class(class_definition)
    print(methods)  # Output: ['method_one', 'method_two', 'method_three']