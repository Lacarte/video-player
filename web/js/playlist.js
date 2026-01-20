/**
 * Playlist module
 * Handles sidebar navigation, chapter expansion, and video selection
 */

const Playlist = {
    // DOM elements
    container: null,
    collapseBtn: null,
    searchInput: null,
    clearSearchBtn: null,

    // State
    playlist: null,
    allVideos: [],  // Flat list of all videos for navigation
    expandedChapters: new Set(),
    searchQuery: '',
    searchDebounceTimer: null,

    /**
     * Initialize playlist module
     */
    init() {
        this.container = document.getElementById('playlist-container');
        this.collapseBtn = document.getElementById('btn-collapse-all');
        this.searchInput = document.getElementById('search-input');
        this.clearSearchBtn = document.getElementById('btn-clear-search');

        this.collapseBtn.addEventListener('click', () => this.collapseAll());

        // Search functionality
        this.searchInput.addEventListener('input', (e) => {
            clearTimeout(this.searchDebounceTimer);
            this.searchDebounceTimer = setTimeout(() => {
                this.search(e.target.value);
            }, 150);
        });

        this.clearSearchBtn.addEventListener('click', () => {
            this.searchInput.value = '';
            this.clearSearchBtn.classList.remove('visible');
            this.search('');
            this.searchInput.focus();
        });

        // Keyboard shortcut: Ctrl+F or / to focus search
        document.addEventListener('keydown', (e) => {
            if ((e.ctrlKey && e.key === 'f') || (e.key === '/' && !e.target.matches('input, select, textarea'))) {
                e.preventDefault();
                this.searchInput.focus();
                this.searchInput.select();
            }
            // Escape to clear search
            if (e.key === 'Escape' && document.activeElement === this.searchInput) {
                this.searchInput.value = '';
                this.search('');
                this.searchInput.blur();
            }
        });
    },

    /**
     * Load playlist data and render
     * @param {Object} data - Playlist data from API
     */
    load(data) {
        this.playlist = data;
        this.allVideos = this.flattenVideos(data);
        this.render();
    },

    /**
     * Flatten all videos into a single array for easy navigation
     * @param {Object} data - Playlist data
     * @returns {Array} - Flat array of video objects
     */
    flattenVideos(data) {
        const videos = [];

        // Helper to extract leading number for sorting
        const getLeadingNum = (title) => parseInt(title.match(/^(\d+)/)?.[1]) || 999999;

        // Process chapter videos recursively
        const processChapter = (chapter, parentPath = '') => {
            const chapterPath = parentPath ? `${parentPath}/${chapter.title}` : chapter.title;

            if (chapter.videos) {
                for (const video of chapter.videos) {
                    videos.push({ ...video, chapter: chapterPath, chapterObj: chapter });
                }
            }

            if (chapter.children) {
                for (const child of chapter.children) {
                    processChapter(child, chapterPath);
                }
            }
        };

        // Combine root videos and chapters, sort by leading number (same as render)
        const rootVideos = (data.videos || []).map(v => ({ type: 'video', item: v, title: v.title }));
        const chapters = (data.chapters || []).map(c => ({ type: 'chapter', item: c, title: c.title }));
        const combined = [...rootVideos, ...chapters].sort((a, b) => {
            const numA = getLeadingNum(a.title);
            const numB = getLeadingNum(b.title);
            if (numA !== numB) return numA - numB;
            return a.title.localeCompare(b.title);
        });

        // Process in sorted order
        for (const entry of combined) {
            if (entry.type === 'video') {
                videos.push({ ...entry.item, chapter: null });
            } else {
                processChapter(entry.item);
            }
        }

        return videos;
    },

    /**
     * Render the playlist
     */
    render() {
        if (!this.playlist) return;

        let html = '';

        // Combine root videos and chapters, then sort by title using natural sort
        const rootVideos = (this.playlist.videos || []).map(v => ({ type: 'video', item: v, title: v.title }));
        const chapters = (this.playlist.chapters || []).map(c => ({ type: 'chapter', item: c, title: c.title }));
        const combined = [...rootVideos, ...chapters].sort((a, b) => {
            // Natural sort: extract leading number if present
            const numA = parseInt(a.title.match(/^(\d+)/)?.[1]) || 999999;
            const numB = parseInt(b.title.match(/^(\d+)/)?.[1]) || 999999;
            if (numA !== numB) return numA - numB;
            return a.title.localeCompare(b.title);
        });

        // Render items in order
        for (const entry of combined) {
            if (entry.type === 'video') {
                html += this.renderVideoItem(entry.item);
            } else {
                html += this.renderChapter(entry.item);
            }
        }

        this.container.innerHTML = html;
        this.attachEventListeners();
    },

    /**
     * Render a chapter (recursive for sub-chapters)
     * @param {Object} chapter - Chapter object
     * @param {number} depth - Nesting depth
     * @returns {string} - HTML string
     */
    renderChapter(chapter, depth = 0) {
        const chapterId = this.getChapterId(chapter);
        const isExpanded = this.expandedChapters.has(chapterId);
        const completion = this.getChapterCompletion(chapter);
        const videoCount = chapter.video_count || chapter.videos?.length || 0;
        const docCount = chapter.documents?.length || 0;
        const duration = this.formatDuration(chapter.duration);
        const escapedId = this.escapeHtml(chapterId);

        // Show video count if has videos, otherwise show document count
        const metaInfo = videoCount > 0
            ? `<span>${videoCount} videos</span><span>${duration}</span>`
            : (docCount > 0 ? `<span>${docCount} docs</span>` : '');

        // Build the folder path for opening
        const folderPath = chapter.path ? `/media/${chapter.path}` : '';

        let html = `
            <div class="playlist-chapter" data-chapter-id="${escapedId}" style="margin-left: ${depth * 12}px;">
                <div class="chapter-header ${isExpanded ? 'expanded' : ''}" data-chapter="${escapedId}" title="${this.escapeHtml(chapter.title)}">
                    <span class="chapter-toggle ${isExpanded ? 'expanded' : ''}">▶</span>
                    <span class="chapter-title">${this.escapeHtml(chapter.title)}</span>
                    <div class="chapter-meta">
                        ${metaInfo}
                    </div>
                    ${videoCount > 0 ? `<div class="chapter-progress"><div class="chapter-progress-bar" style="width: ${completion}%"></div></div>` : ''}
                    <button class="btn-open-folder" data-folder-path="${this.escapeHtml(folderPath)}" title="Open folder">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                        </svg>
                    </button>
                </div>
                <div class="chapter-videos ${isExpanded ? 'expanded' : ''}" data-chapter-content="${escapedId}">
        `;

        // Videos in this chapter
        if (chapter.videos) {
            for (const video of chapter.videos) {
                html += this.renderVideoItem(video);
            }
        }

        // Documents in this chapter
        if (chapter.documents && chapter.documents.length > 0) {
            for (const doc of chapter.documents) {
                html += this.renderDocumentItem(doc);
            }
        }

        // Sub-chapters
        if (chapter.children) {
            for (const child of chapter.children) {
                html += this.renderChapter(child, depth + 1);
            }
        }

        html += '</div></div>';
        return html;
    },

    /**
     * Render a document item in the playlist
     * @param {Object} doc - Document object
     * @returns {string} - HTML string
     */
    renderDocumentItem(doc) {
        const icon = this.getDocumentIcon(doc.type);
        return `
            <div class="document-item playlist-doc-item"
                 data-doc-path="${this.escapeHtml(doc.path)}"
                 data-doc-type="${doc.type}"
                 data-doc-title="${this.escapeHtml(doc.title)}"
                 data-doc-file="${this.escapeHtml(doc.file)}">
                <span class="doc-icon">${icon}</span>
                <span class="doc-name">${this.escapeHtml(doc.title)}</span>
                <button class="btn-open-folder" data-path="${this.escapeHtml(doc.path)}" title="Open folder">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                    </svg>
                </button>
            </div>
        `;
    },

    /**
     * Get icon for document type
     * @param {string} type - Document type
     * @returns {string} - Emoji icon
     */
    getDocumentIcon(type) {
        const icons = {
            'pdf': '📕',
            'html': '🌐',
            'image': '🖼️',
            'text': '📝',
            'json': '📋',
            'zip': '📦',
            'docx': '📘',
            'other': '📄'
        };
        return icons[type] || '📄';
    },

    /**
     * Render a video item
     * @param {Object} video - Video object
     * @returns {string} - HTML string
     */
    renderVideoItem(video) {
        const isCompleted = Progress.isVideoCompleted(video.path);
        const isActive = App.state.currentVideo?.path === video.path;
        const duration = this.formatDuration(video.duration);
        const statusIcon = isCompleted ? '✓' : '○';

        // Show full filename (video.file) in tooltip, display clean title
        const tooltipText = video.file || video.title;

        // Use encodeURIComponent for data attribute to preserve special chars
        return `
            <div class="video-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}"
                 data-video-path="${encodeURIComponent(video.path)}"
                 title="${this.escapeHtml(tooltipText)}">
                <span class="video-status">${statusIcon}</span>
                <div class="video-info">
                    <div class="video-title">${this.escapeHtml(video.title)}</div>
                    <div class="video-duration">${duration}</div>
                </div>
                <button class="btn-open-folder" data-path="${this.escapeHtml(video.path)}" title="Open folder">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path>
                    </svg>
                </button>
            </div>
        `;
    },

    /**
     * Attach event listeners to playlist items
     */
    attachEventListeners() {
        // Chapter headers
        this.container.querySelectorAll('.chapter-header').forEach(header => {
            header.addEventListener('click', (e) => {
                // Ignore if clicking the folder button
                if (e.target.closest('.btn-open-folder')) return;
                e.stopPropagation(); // Prevent parent chapters from toggling
                const chapterId = header.dataset.chapter;
                this.toggleChapter(chapterId);
            });
        });

        // Video items
        this.container.querySelectorAll('.video-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Ignore if clicking the folder button
                if (e.target.closest('.btn-open-folder')) return;
                e.stopPropagation(); // Prevent chapter toggle
                const videoPath = decodeURIComponent(item.dataset.videoPath);
                const video = this.allVideos.find(v => v.path === videoPath);
                if (video) {
                    App.playVideo(video);
                }
            });
        });

        // Document items in playlist
        this.container.querySelectorAll('.playlist-doc-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Ignore if clicking the folder button
                if (e.target.closest('.btn-open-folder')) return;
                e.stopPropagation(); // Prevent chapter toggle
                Modal.open({
                    type: item.dataset.docType,
                    title: item.dataset.docTitle,
                    path: item.dataset.docPath,
                    file: item.dataset.docFile
                });
            });
        });

        // Open folder buttons
        this.container.querySelectorAll('.btn-open-folder').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation(); // Prevent any parent handlers
                const path = btn.dataset.path || btn.dataset.folderPath;
                if (path) {
                    this.openFolder(path);
                }
            });
        });
    },

    /**
     * Open folder containing a file
     * @param {string} path - File or folder path
     */
    openFolder(path) {
        fetch('/api/open-folder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path })
        }).catch(err => console.error('Failed to open folder:', err));
    },

    /**
     * Toggle chapter expansion
     * @param {string} chapterId - Chapter ID
     */
    toggleChapter(chapterId) {
        const escapedId = CSS.escape(chapterId);
        const header = this.container.querySelector(`[data-chapter="${escapedId}"]`);
        const content = this.container.querySelector(`[data-chapter-content="${escapedId}"]`);
        const toggle = header?.querySelector('.chapter-toggle');

        if (!header || !content) return;

        if (this.expandedChapters.has(chapterId)) {
            this.expandedChapters.delete(chapterId);
            header.classList.remove('expanded');
            content.classList.remove('expanded');
            toggle?.classList.remove('expanded');
        } else {
            this.expandedChapters.add(chapterId);
            header.classList.add('expanded');
            content.classList.add('expanded');
            toggle?.classList.add('expanded');
        }
    },

    /**
     * Expand chapter containing a video (including all parent chapters)
     * @param {Object} video - Video object
     */
    expandToVideo(video) {
        if (!video.chapterObj) return;

        // Find all chapters that need to be expanded by traversing the chapter path
        const findAndExpandPath = (chapters, targetPath, pathSoFar = []) => {
            for (const chapter of chapters) {
                const chapterId = this.getChapterId(chapter);

                if (chapter.path === video.chapterObj.path) {
                    // Found the target chapter - expand all chapters in path
                    [...pathSoFar, chapterId].forEach(id => {
                        if (!this.expandedChapters.has(id)) {
                            this.toggleChapter(id);
                        }
                    });
                    return true;
                }

                if (chapter.children && chapter.children.length > 0) {
                    if (findAndExpandPath(chapter.children, targetPath, [...pathSoFar, chapterId])) {
                        return true;
                    }
                }
            }
            return false;
        };

        if (this.playlist?.chapters) {
            findAndExpandPath(this.playlist.chapters, video.chapterObj.path);
        }
    },

    /**
     * Collapse all chapters
     */
    collapseAll() {
        this.expandedChapters.clear();
        this.render();
    },

    /**
     * Update active video highlighting
     * @param {Object} video - Current video
     */
    setActiveVideo(video) {
        // Remove previous active
        this.container.querySelectorAll('.video-item.active').forEach(item => {
            item.classList.remove('active');
        });

        // Add new active
        if (video) {
            const encodedPath = encodeURIComponent(video.path);
            const item = this.container.querySelector(`[data-video-path="${CSS.escape(encodedPath)}"]`);
            if (item) {
                item.classList.add('active');
                // Scroll into view
                item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            }
        }
    },

    /**
     * Mark a video as completed in UI
     * @param {string} videoPath - Video path
     */
    markVideoCompleted(videoPath) {
        const encodedPath = encodeURIComponent(videoPath);
        const item = this.container.querySelector(`[data-video-path="${CSS.escape(encodedPath)}"]`);
        if (item) {
            item.classList.add('completed');
            item.querySelector('.video-status').textContent = '✓';
        }

        // Update chapter progress bars
        this.updateChapterProgress();
    },

    /**
     * Update all chapter progress bars
     */
    updateChapterProgress() {
        this.container.querySelectorAll('.playlist-chapter').forEach(chapterEl => {
            const chapterId = chapterEl.dataset.chapterId;
            // Find chapter in data
            const chapter = this.findChapterById(chapterId);
            if (chapter) {
                const completion = this.getChapterCompletion(chapter);
                const bar = chapterEl.querySelector('.chapter-progress-bar');
                if (bar) {
                    bar.style.width = `${completion}%`;
                }
            }
        });
    },

    /**
     * Get chapter completion percentage
     * @param {Object} chapter - Chapter object
     * @returns {number} - Completion percentage
     */
    getChapterCompletion(chapter) {
        const videos = [];

        // Collect all videos in chapter (including sub-chapters)
        const collectVideos = (ch) => {
            if (ch.videos) {
                videos.push(...ch.videos);
            }
            if (ch.children) {
                for (const child of ch.children) {
                    collectVideos(child);
                }
            }
        };

        collectVideos(chapter);
        return Progress.calculateCompletion(videos);
    },

    /**
     * Find chapter by ID
     * @param {string} chapterId - Chapter ID
     * @returns {Object|null} - Chapter object
     */
    findChapterById(chapterId) {
        const find = (chapters) => {
            for (const ch of chapters) {
                if (this.getChapterId(ch) === chapterId) {
                    return ch;
                }
                if (ch.children) {
                    const found = find(ch.children);
                    if (found) return found;
                }
            }
            return null;
        };

        return this.playlist?.chapters ? find(this.playlist.chapters) : null;
    },

    /**
     * Generate unique ID for a chapter
     * @param {Object} chapter - Chapter object
     * @returns {string} - Unique ID (sanitized for use in CSS selectors)
     */
    getChapterId(chapter) {
        const id = chapter.path || chapter.title;
        // Replace backslashes/forward slashes and special chars that break CSS selectors
        // Using hex escape \x5c for backslash, \x2f for forward slash
        return id.replace(/[\x5c\x2f]/g, '_').replace(/[^\w\s-]/g, '');
    },

    /**
     * Get next video in playlist
     * @param {Object} currentVideo - Current video
     * @returns {Object|null} - Next video or null
     */
    getNextVideo(currentVideo) {
        if (!currentVideo) return this.allVideos[0] || null;

        const index = this.allVideos.findIndex(v => v.path === currentVideo.path);
        if (index >= 0 && index < this.allVideos.length - 1) {
            return this.allVideos[index + 1];
        }
        return null;
    },

    /**
     * Get previous video in playlist
     * @param {Object} currentVideo - Current video
     * @returns {Object|null} - Previous video or null
     */
    getPreviousVideo(currentVideo) {
        if (!currentVideo) return null;

        const index = this.allVideos.findIndex(v => v.path === currentVideo.path);
        if (index > 0) {
            return this.allVideos[index - 1];
        }
        return null;
    },

    /**
     * Get video by path
     * @param {string} path - Video path
     * @returns {Object|null} - Video object
     */
    getVideoByPath(path) {
        return this.allVideos.find(v => v.path === path) || null;
    },

    /**
     * Format duration in seconds to human readable
     * @param {number} seconds - Duration in seconds
     * @returns {string} - Formatted duration
     */
    formatDuration(seconds) {
        if (!seconds || seconds === 0) return '--:--';

        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);

        if (hours > 0) {
            return `${hours}:${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        }
        return `${mins}:${secs.toString().padStart(2, '0')}`;
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
    },

    /**
     * Search videos and chapters
     * @param {string} query - Search query
     */
    search(query) {
        this.searchQuery = query.trim().toLowerCase();

        // Toggle clear button visibility
        if (this.searchQuery) {
            this.clearSearchBtn.classList.add('visible');
        } else {
            this.clearSearchBtn.classList.remove('visible');
        }

        if (!this.searchQuery) {
            // No search - render normal playlist
            this.render();
            return;
        }

        // Find matching videos
        const matchingVideos = this.allVideos.filter(video => {
            const titleMatch = video.title.toLowerCase().includes(this.searchQuery);
            const fileMatch = video.file?.toLowerCase().includes(this.searchQuery);
            const chapterMatch = video.chapter?.toLowerCase().includes(this.searchQuery);
            return titleMatch || fileMatch || chapterMatch;
        });

        this.renderSearchResults(matchingVideos);
    },

    /**
     * Render search results
     * @param {Array} videos - Matching videos
     */
    renderSearchResults(videos) {
        if (videos.length === 0) {
            this.container.innerHTML = `
                <div class="no-results">
                    <div class="no-results-icon">🔍</div>
                    <div>No videos found for "${this.escapeHtml(this.searchQuery)}"</div>
                </div>
            `;
            return;
        }

        let html = `<div class="search-results-info">${videos.length} result${videos.length !== 1 ? 's' : ''} for "${this.escapeHtml(this.searchQuery)}"</div>`;

        for (const video of videos) {
            const isCompleted = Progress.isVideoCompleted(video.path);
            const isActive = App.state.currentVideo?.path === video.path;
            const duration = this.formatDuration(video.duration);
            const statusIcon = isCompleted ? '✓' : '○';

            // Highlight matching text
            const highlightedTitle = this.highlightMatch(video.title, this.searchQuery);
            const chapterInfo = video.chapter ? `<div class="video-chapter-path">${this.highlightMatch(video.chapter, this.searchQuery)}</div>` : '';

            html += `
                <div class="video-item ${isActive ? 'active' : ''} ${isCompleted ? 'completed' : ''}"
                     data-video-path="${encodeURIComponent(video.path)}"
                     title="${this.escapeHtml(video.file || video.title)}">
                    <span class="video-status">${statusIcon}</span>
                    <div class="video-info">
                        <div class="video-title">${highlightedTitle}</div>
                        ${chapterInfo}
                        <div class="video-duration">${duration}</div>
                    </div>
                </div>
            `;
        }

        this.container.innerHTML = html;
        this.attachEventListeners();
    },

    /**
     * Highlight matching text in string
     * @param {string} text - Original text
     * @param {string} query - Search query
     * @returns {string} - HTML with highlighted matches
     */
    highlightMatch(text, query) {
        if (!query) return this.escapeHtml(text);

        const escaped = this.escapeHtml(text);
        const regex = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
        return escaped.replace(regex, '<span class="search-highlight">$1</span>');
    }
};

// Export for use in other modules
window.Playlist = Playlist;
