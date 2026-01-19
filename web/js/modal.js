/**
 * Modal module for document viewing
 * Supports: PDF, Images, Text, JSON, ZIP (file list)
 */

const Modal = {
    // DOM elements
    modal: null,
    backdrop: null,
    title: null,
    body: null,
    downloadBtn: null,
    closeBtn: null,
    closeBtnFooter: null,

    /**
     * Initialize modal module
     */
    init() {
        this.modal = document.getElementById('doc-modal');
        this.backdrop = document.getElementById('modal-backdrop');
        this.title = document.getElementById('modal-title');
        this.body = document.getElementById('modal-body');
        this.downloadBtn = document.getElementById('modal-download');
        this.closeBtn = document.getElementById('modal-close');
        this.closeBtnFooter = document.getElementById('modal-close-btn');

        // Event listeners
        this.backdrop.addEventListener('click', () => this.close());
        this.closeBtn.addEventListener('click', () => this.close());
        this.closeBtnFooter.addEventListener('click', () => this.close());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                this.close();
            }
        });
    },

    /**
     * Open modal with document content
     * @param {Object} doc - Document object { type, title, path, file }
     */
    open(doc) {
        this.title.textContent = doc.title;
        this.downloadBtn.href = doc.path;
        this.downloadBtn.download = doc.file;

        // Clear previous content
        this.body.innerHTML = '<div class="loading-content"><div class="loading-spinner"></div><div class="loading-text">Loading...</div></div>';

        // Load content based on type
        switch (doc.type) {
            case 'pdf':
                this.loadPDF(doc.path);
                break;
            case 'image':
                this.loadImage(doc.path, doc.title);
                break;
            case 'text':
                this.loadText(doc.path);
                break;
            case 'json':
                this.loadJSON(doc.path);
                break;
            case 'zip':
                this.loadZipInfo(doc);
                break;
            default:
                this.loadUnsupported(doc);
        }

        this.modal.classList.add('show');
    },

    /**
     * Close modal
     */
    close() {
        this.modal.classList.remove('show');
        // Clear body after transition
        setTimeout(() => {
            this.body.innerHTML = '';
        }, 300);
    },

    /**
     * Load PDF in iframe
     * @param {string} path - PDF path
     */
    loadPDF(path) {
        this.body.innerHTML = `<iframe src="${path}" title="PDF Viewer"></iframe>`;
    },

    /**
     * Load image
     * @param {string} path - Image path
     * @param {string} title - Image title
     */
    loadImage(path, title) {
        const img = document.createElement('img');
        img.src = path;
        img.alt = title;
        img.onload = () => {
            this.body.innerHTML = '';
            this.body.appendChild(img);
        };
        img.onerror = () => {
            this.body.innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><div class="empty-text">Failed to load image</div></div>';
        };
    },

    /**
     * Load text file
     * @param {string} path - Text file path
     */
    async loadText(path) {
        try {
            const response = await fetch(path);
            if (!response.ok) throw new Error('Failed to load');
            const text = await response.text();
            this.body.innerHTML = `<pre>${this.escapeHtml(text)}</pre>`;
        } catch (e) {
            this.body.innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><div class="empty-text">Failed to load text file</div></div>';
        }
    },

    /**
     * Load JSON file with formatting
     * @param {string} path - JSON file path
     */
    async loadJSON(path) {
        try {
            const response = await fetch(path);
            if (!response.ok) throw new Error('Failed to load');
            const json = await response.json();
            const formatted = JSON.stringify(json, null, 2);
            this.body.innerHTML = `<pre>${this.escapeHtml(formatted)}</pre>`;
        } catch (e) {
            this.body.innerHTML = '<div class="empty-state"><div class="empty-icon">❌</div><div class="empty-text">Failed to load JSON file</div></div>';
        }
    },

    /**
     * Show ZIP file info (cannot extract in browser)
     * @param {Object} doc - Document object
     */
    loadZipInfo(doc) {
        this.body.innerHTML = `
            <div class="empty-state" style="padding: 60px 20px;">
                <div class="empty-icon">📦</div>
                <div class="empty-text" style="margin-bottom: 16px;">Archive File</div>
                <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 20px;">
                    ZIP files cannot be previewed in the browser.<br>
                    Use the download button to save and extract locally.
                </p>
                <div style="background: var(--bg-tertiary); padding: 16px; border-radius: 8px; font-family: monospace; font-size: 0.85rem;">
                    ${this.escapeHtml(doc.file)}
                </div>
            </div>
        `;
    },

    /**
     * Show unsupported file type
     * @param {Object} doc - Document object
     */
    loadUnsupported(doc) {
        this.body.innerHTML = `
            <div class="empty-state" style="padding: 60px 20px;">
                <div class="empty-icon">📄</div>
                <div class="empty-text" style="margin-bottom: 16px;">Preview Not Available</div>
                <p style="color: var(--text-muted); font-size: 0.85rem; margin-bottom: 20px;">
                    This file type cannot be previewed in the browser.<br>
                    Use the download button to open locally.
                </p>
                <div style="background: var(--bg-tertiary); padding: 16px; border-radius: 8px; font-family: monospace; font-size: 0.85rem;">
                    ${this.escapeHtml(doc.file)}
                </div>
            </div>
        `;
    },

    /**
     * Escape HTML special characters
     * @param {string} text - Raw text
     * @returns {string} - Escaped text
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Export for use in other modules
window.Modal = Modal;
