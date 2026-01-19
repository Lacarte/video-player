/**
 * Modal module for document viewing
 * Supports: PDF, HTML, Images, Text, JSON, ZIP (file list)
 */

const Modal = {
    // DOM elements
    modal: null,
    modalContent: null,
    backdrop: null,
    title: null,
    body: null,
    downloadBtn: null,
    closeBtn: null,
    closeBtnFooter: null,
    fullscreenBtn: null,

    /**
     * Initialize modal module
     */
    init() {
        this.modal = document.getElementById('doc-modal');
        this.modalContent = this.modal.querySelector('.modal-content');
        this.backdrop = document.getElementById('modal-backdrop');
        this.title = document.getElementById('modal-title');
        this.body = document.getElementById('modal-body');
        this.downloadBtn = document.getElementById('modal-download');
        this.closeBtn = document.getElementById('modal-close');
        this.closeBtnFooter = document.getElementById('modal-close-btn');
        this.fullscreenBtn = document.getElementById('modal-fullscreen');

        // Event listeners
        this.backdrop.addEventListener('click', () => this.close());
        this.closeBtn.addEventListener('click', () => this.close());
        this.closeBtnFooter.addEventListener('click', () => this.close());
        this.fullscreenBtn?.addEventListener('click', () => this.toggleFullscreen());

        // Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('show')) {
                // If in fullscreen, exit fullscreen first
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    this.close();
                }
            }
        });

        // Update button icon when fullscreen changes
        document.addEventListener('fullscreenchange', () => this.updateFullscreenIcon());
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
            case 'html':
                this.loadHTML(doc.path);
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
        // Exit fullscreen if active
        if (document.fullscreenElement) {
            document.exitFullscreen();
        }
        this.modal.classList.remove('show');
        // Clear body after transition
        setTimeout(() => {
            this.body.innerHTML = '';
        }, 300);
    },

    /**
     * Toggle fullscreen mode for modal content
     */
    toggleFullscreen() {
        if (document.fullscreenElement) {
            document.exitFullscreen();
        } else {
            this.modalContent.requestFullscreen().catch(err => {
                console.log('Fullscreen not supported:', err);
            });
        }
    },

    /**
     * Update fullscreen button icon based on current state
     */
    updateFullscreenIcon() {
        if (!this.fullscreenBtn) return;

        const isFullscreen = !!document.fullscreenElement;
        this.fullscreenBtn.innerHTML = isFullscreen
            ? `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="4 14 10 14 10 20"></polyline>
                <polyline points="20 10 14 10 14 4"></polyline>
                <line x1="14" y1="10" x2="21" y2="3"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
               </svg>`
            : `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="15 3 21 3 21 9"></polyline>
                <polyline points="9 21 3 21 3 15"></polyline>
                <line x1="21" y1="3" x2="14" y2="10"></line>
                <line x1="3" y1="21" x2="10" y2="14"></line>
               </svg>`;
        this.fullscreenBtn.title = isFullscreen ? 'Exit Fullscreen' : 'Toggle Fullscreen';
    },

    /**
     * Load PDF in iframe
     * @param {string} path - PDF path
     */
    loadPDF(path) {
        this.body.innerHTML = `<iframe src="${path}" title="PDF Viewer"></iframe>`;
    },

    /**
     * Load HTML in iframe
     * @param {string} path - HTML file path
     */
    loadHTML(path) {
        this.body.innerHTML = `<iframe src="${path}" title="HTML Viewer"></iframe>`;
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
