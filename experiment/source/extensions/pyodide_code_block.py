"""
Sphinx extension for embedding executable Python code using Pyodide
"""


from docutils import nodes
from docutils.parsers.rst import Directive, directives
from sphinx.util import logging

logger = logging.getLogger(__name__)


class pyodide_code_block(nodes.General, nodes.Element):
    """Custom node for Pyodide code blocks"""

    pass


class PyodideCodeDirective(Directive):
    """Directive for Pyodide executable code blocks"""

    has_content = True
    required_arguments = 0
    optional_arguments = 0
    final_argument_whitespace = False
    option_spec = {
        "linenos": directives.flag,
        "emphasize-lines": directives.unchanged,
        "caption": directives.unchanged,
    }

    def run(self):
        # Get the code content
        code = "\n".join(self.content)
        if not code.strip():
            logger.warning("Empty pyodide-code directive")
            return []

        # Create the custom node
        node = pyodide_code_block()
        node["code"] = code
        node["linenos"] = "linenos" in self.options
        node["emphasize_lines"] = self.options.get("emphasize-lines", "")
        node["caption"] = self.options.get("caption", "")

        # Add source and line information for better error messages
        node.source, node.line = self.state_machine.get_source_and_line(self.lineno)

        return [node]


def visit_pyodide_code_block_html(self, node):
    """HTML visitor for pyodide_code_block nodes"""

    # Generate a unique ID for this code block
    block_id = f"pyodide-{self.builder.env.new_serialno('pyodide')}"

    # Build the HTML structure
    html_parts = ['<div class="pyodide-code-container">']

    # Add caption if present
    if node["caption"]:
        html_parts.append(f'<div class="pyodide-caption">{node["caption"]}</div>')

    # Add code display area
    html_parts.append('<div class="pyodide-code-wrapper">')
    html_parts.append(f'<pre class="pyodide-code" id="{block_id}-code">')

    # Add line numbers if requested
    if node["linenos"]:
        lines = node["code"].split("\n")
        for i, line in enumerate(lines, 1):
            html_parts.append(
                f'<span class="lineno">{i:3d}</span> {self.encode(line)}\n'
            )
    else:
        html_parts.append(self.encode(node["code"]))

    html_parts.append("</pre>")

    # Store the code in a hidden element for JavaScript to access
    html_parts.append(
        f'<script type="text/python" id="{block_id}-source" style="display:none">{node["code"]}</script>'
    )

    # Add control buttons
    html_parts.append('<div class="pyodide-controls">')
    html_parts.append(
        f'<button class="pyodide-run-button" onclick="runPyodideCode(\'{block_id}\')">実行</button>'
    )
    html_parts.append(
        f'<button class="pyodide-clear-button" onclick="clearPyodideOutput(\'{block_id}\')">クリア</button>'
    )
    html_parts.append("</div>")

    # Add output area
    html_parts.append(f'<div class="pyodide-output" id="{block_id}-output"></div>')
    html_parts.append("</div>")  # close wrapper
    html_parts.append("</div>")  # close container

    self.body.append("".join(html_parts))


def depart_pyodide_code_block_html(self, node):
    """Departure function for pyodide_code_block nodes"""
    pass  # Nothing to do on departure


def add_pyodide_assets(app, pagename, templatename, context, doctree):
    """Add Pyodide JavaScript and CSS to the page"""

    if doctree is None:
        return

    # Check if this page has any Pyodide code blocks
    if not any(isinstance(node, pyodide_code_block) for node in doctree.traverse()):
        return

    # Add CSS
    css = """
    <style>
    .pyodide-code-container {
        margin: 1em 0;
        border: 1px solid #e0e0e0;
        border-radius: 4px;
        overflow: hidden;
    }
    
    .pyodide-caption {
        background-color: #f5f5f5;
        padding: 0.5em 1em;
        font-weight: bold;
        border-bottom: 1px solid #e0e0e0;
    }
    
    .pyodide-code-wrapper {
        position: relative;
    }
    
    .pyodide-code {
        margin: 0;
        padding: 1em;
        background-color: #f8f8f8;
        overflow-x: auto;
    }
    
    .pyodide-code .lineno {
        color: #666;
        user-select: none;
    }
    
    .pyodide-controls {
        padding: 0.5em 1em;
        background-color: #f5f5f5;
        border-top: 1px solid #e0e0e0;
    }
    
    .pyodide-run-button,
    .pyodide-clear-button {
        padding: 0.25em 1em;
        margin-right: 0.5em;
        border: 1px solid #ccc;
        border-radius: 3px;
        background-color: #fff;
        cursor: pointer;
    }
    
    .pyodide-run-button:hover,
    .pyodide-clear-button:hover {
        background-color: #e0e0e0;
    }
    
    .pyodide-output {
        padding: 1em;
        background-color: #fff;
        border-top: 1px solid #e0e0e0;
        min-height: 2em;
        white-space: pre-wrap;
        font-family: monospace;
        display: none;
    }
    
    .pyodide-output.has-content {
        display: block;
    }
    
    .pyodide-output.error {
        color: #d32f2f;
    }
    
    .pyodide-loading {
        color: #666;
        font-style: italic;
    }
    </style>
    """

    # Add JavaScript
    js = """
    <script src="https://cdn.jsdelivr.net/pyodide/v0.27.2/full/pyodide.js"></script>
    <script>
    let pyodideReadyPromise = null;
    let pyodide = null;
    
    // Initialize Pyodide
    async function initPyodide() {
        if (!pyodideReadyPromise) {
            pyodideReadyPromise = loadPyodide({
                indexURL: "https://cdn.jsdelivr.net/pyodide/v0.27.2/full/"
            });
        }
        return pyodideReadyPromise;
    }
    
    // Run Python code
    async function runPyodideCode(blockId) {
        const outputElement = document.getElementById(blockId + '-output');
        const codeElement = document.getElementById(blockId + '-source');
        
        if (!outputElement || !codeElement) {
            console.error('Required elements not found for block:', blockId);
            return;
        }
        
        const code = codeElement.textContent;
        
        outputElement.innerHTML = '<span class="pyodide-loading">Pyodideを読み込み中...</span>';
        outputElement.classList.add('has-content');
        outputElement.classList.remove('error');
        
        try {
            pyodide = await initPyodide();
            console.log('Pyodide loaded, running code:', code);
            
            // Capture output - using separate strings to avoid template literal issues
            const setupCode = 'import sys\\n' +
                            'from io import StringIO\\n' +
                            '_pyodide_output = StringIO()\\n' +
                            '_pyodide_stdout = sys.stdout\\n' +
                            'sys.stdout = _pyodide_output';
            
            pyodide.runPython(setupCode);
            
            // Run the user code
            try {
                pyodide.runPython(code);
                
                // Get the output
                const getOutputCode = 'sys.stdout = _pyodide_stdout\\n' +
                                    '_pyodide_output.getvalue()';
                const output = pyodide.runPython(getOutputCode);
                
                outputElement.textContent = output || '(出力なし)';
                console.log('Code execution successful, output:', output);
            } catch (error) {
                console.error('Python execution error:', error);
                outputElement.textContent = 'エラー: ' + error.message;
                outputElement.classList.add('error');
            }
            
        } catch (error) {
            console.error('Pyodide initialization error:', error);
            outputElement.textContent = 'Pyodideの初期化エラー: ' + error.message;
            outputElement.classList.add('error');
        }
    }
    
    // Clear output
    function clearPyodideOutput(blockId) {
        const outputElement = document.getElementById(blockId + '-output');
        outputElement.textContent = '';
        outputElement.classList.remove('has-content', 'error');
    }
    
    // Initialize Pyodide when page loads
    document.addEventListener('DOMContentLoaded', function() {
        initPyodide().catch(console.error);
    });
    </script>
    """

    # Add assets to the page context
    if "body" not in context:
        context["body"] = ""

    context["body"] = css + js + context["body"]


def setup(app):
    """Setup the Sphinx extension"""

    # Add the directive
    app.add_directive("pyodide-code", PyodideCodeDirective)

    # Add the node and visitors
    app.add_node(
        pyodide_code_block,
        html=(visit_pyodide_code_block_html, depart_pyodide_code_block_html),
    )

    # Connect to add assets
    app.connect("html-page-context", add_pyodide_assets)

    # Add configuration values
    app.add_config_value("pyodide_version", "0.27.2", "html")

    return {
        "version": "0.1",
        "parallel_read_safe": True,
        "parallel_write_safe": True,
    }
