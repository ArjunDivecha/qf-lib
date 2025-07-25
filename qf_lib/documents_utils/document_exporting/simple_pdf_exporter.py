#     Copyright 2016-present CERN – European Organization for Nuclear Research
#
#     Licensed under the Apache License, Version 2.0 (the "License");
#     you may not use this file except in compliance with the License.
#     You may obtain a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#     Unless required by applicable law or agreed to in writing, software
#     distributed under the License is distributed on an "AS IS" BASIS,
#     WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#     See the License for the specific language governing permissions and
#     limitations under the License.

import os
from os.path import join, abspath, dirname
from typing import List
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import base64
import re
from io import BytesIO
from PIL import Image
import numpy as np

from qf_lib.common.utils.logging.qf_parent_logger import qf_logger
from qf_lib.documents_utils.document_exporting.document import Document
from qf_lib.documents_utils.document_exporting.document_exporter import DocumentExporter
from qf_lib.settings import Settings
from qf_lib.starting_dir import get_starting_dir_abs_path


class SimplePDFExporter(DocumentExporter):
    """
    A simpler PDF exporter that uses matplotlib to generate PDF files.
    This replaces the WeasyPrint-based PDFExporter with a lighter alternative.
    """

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self.logger = qf_logger.getChild(self.__class__.__name__)

    def generate(self, documents: List[Document], export_dir: str, filename: str,
                 include_table_of_contents=False, css_file_names: List[str] = None) -> str:
        """
        Generates a PDF document from the provided documents.

        Parameters
        ----------
        documents
            list of documents for which files should be generated
        export_dir
            relative path to the directory (relative to the output root directory) in which the PDF should be saved
        filename
            filename under which the merged document should be saved
        include_table_of_contents
            if True then table of contents will be generated at the beginning of the file
        css_file_names
            names of css files which should be applied for generating the PDF (not used in this implementation)

        Returns
        -------
        the absolute path to the output PDF file that was saved
        """
        documents = [self._merge_documents(documents, filename)]

        # Find the output directory
        output_dir = self.get_output_dir(export_dir)
        output_filename = os.path.join(output_dir, filename.replace('.html', '.pdf'))

        # Create PDF with matplotlib
        with PdfPages(output_filename) as pdf:
            for document in documents:
                if include_table_of_contents:
                    self._add_table_of_contents(document)

                # Generate the full document HTML
                self.logger.info("Generating HTML for PDF...")
                html = document.generate_html()
                
                # Process the HTML and create PDF pages
                self._process_html_content(html, pdf)

        self.logger.info("Rendering PDF in {}...".format(output_filename))
        return output_filename

    def _process_html_content(self, html: str, pdf: PdfPages):
        """
        Process HTML content and add it to the PDF.
        """
        # Extract images from HTML
        images = self._extract_images(html)
        
        # Remove images from HTML for text processing
        html_text = re.sub(r'<img[^>]*>', '', html)
        
        # Convert HTML to text
        text_content = self._convert_html_to_text(html_text)
        
        # Create figure with text content
        fig = plt.figure(figsize=(8.5, 11))  # US Letter size
        fig.text(0.05, 0.95, text_content, fontsize=10, verticalalignment='top', wrap=True)
        fig.text(0.05, 0.05, f"Page 1", fontsize=8, verticalalignment='bottom')
        
        # Save the figure to the PDF
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        # Add images as separate pages
        for i, img_data in enumerate(images):
            img_fig = plt.figure(figsize=(8.5, 11))
            try:
                # Decode base64 image
                img_data = img_data.split(',')[1]  # Remove data:image/...;base64, prefix
                img_bytes = base64.b64decode(img_data)
                img = Image.open(BytesIO(img_bytes))
                
                # Display image
                plt.imshow(img)
                plt.axis('off')
                plt.title(f"Image {i+1}")
                
                # Save image page to PDF
                pdf.savefig(img_fig, bbox_inches='tight')
                plt.close(img_fig)
            except Exception as e:
                self.logger.warning(f"Could not process image {i+1}: {str(e)}")
                plt.close(img_fig)

    def _extract_images(self, html: str) -> List[str]:
        """
        Extract base64 encoded images from HTML.
        """
        images = re.findall(r'<img[^>]*src=(["\'])([^"\']*)\1[^>]*>', html)
        return [img[1] for img in images if img[1].startswith('data:image')]

    def _convert_html_to_text(self, html: str) -> str:
        """
        Convert HTML to a simplified text representation for the PDF.
        This is a basic conversion that strips HTML tags and formats the content.
        """
        # Remove script and style elements
        html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL)
        
        # Replace common HTML tags with formatting
        html = re.sub(r'<br\s*/?>', '\n', html)
        html = re.sub(r'<p[^>]*>', '\n', html)
        html = re.sub(r'</p>', '\n', html)
        html = re.sub(r'<h[1-6][^>]*>', '\n\n', html)
        html = re.sub(r'</h[1-6]>', '\n', html)
        html = re.sub(r'<li[^>]*>', '\n• ', html)
        html = re.sub(r'</li>', '\n', html)
        html = re.sub(r'<td[^>]*>', ' | ', html)
        html = re.sub(r'</td>', ' | ', html)
        html = re.sub(r'<tr[^>]*>', '\n', html)
        html = re.sub(r'</tr>', '\n', html)
        html = re.sub(r'<[^>]+>', '', html)  # Remove all other tags
        
        # Clean up extra whitespace
        html = re.sub(r'\n\s*\n', '\n\n', html)
        html = html.strip()
        
        return html