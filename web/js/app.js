/**
 * Main Application module
 * Handles initialization, state management, and coordination between modules
 */

const App = {
    // DOM elements
    loadingOverlay: null,
    courseTitle: null,
    portBadge: null,
    statVideos: null,
    statDuration: null,
    statProgress: null,
    documentsList: null,
    docCount: null,
    toastContainer: null,

    // State
    state: {
        playlist: null,
        currentVideo: null,
        currentChapter: null,
        isCalculatingDurations: false,
        durationProgress: { current: 0, total: 0 }
    },

    // Duration cache key prefix
    DURATION_CACHE_PREFIX: 'video_player:durations:',

    /**
     * Initialize application
     */
    async init() {
        // Get DOM elements
        this.loadingOverlay = document.getElementById('loading-overlay');
        this.courseTitle = document.getElementById('course-title');
        this.portBadge = document.getElementById('port-badge');
        this.statVideos = document.getElementById('stat-videos');
        this.statDuration = document.getElementById('stat-duration');
        this.statProgress = document.getElementById('stat-progress');
        this.documentsList = document.getElementById('documents-list');
        this.docCount = document.getElementById('doc-count');
        this.toastContainer = document.getElementById('toast-container');

        // Initialize modules
        Modal.init();
        Playlist.init();
        Player.init();
        this.initSidebarResize();

        // Load playlist data
        try {
            await this.loadPlaylist();
            this.hideLoading();
            this.resumeLastVideo();

            // Check if we need to calculate durations
            this.checkAndCalculateDurations();
        } catch (e) {
            console.error('Failed to load playlist:', e);
            this.showToast('Failed to load course data', 'error');
            this.hideLoading();
        }
    },

    /**
     * Load playlist from API
     */
    async loadPlaylist() {
        const response = await fetch('/api/playlist');
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        this.state.playlist = data;

        // Try to load cached durations
        this.loadCachedDurations(data);

        // Update UI
        this.courseTitle.textContent = data.title;
        document.title = `${data.title} - Video Player`;
        this.portBadge.textContent = `Port: ${data.port}`;

        // Load playlist in sidebar
        Playlist.load(data);

        // Update stats
        this.updateStats();

        // Show root documents
        this.showDocuments(data.documents);
    },

    /**
     * Load cached durations from localStorage if hash matches
     */
    loadCachedDurations(data) {
        const cacheKey = this.DURATION_CACHE_PREFIX + data.root_path;
        const cached = localStorage.getItem(cacheKey);

        if (!cached) return false;

        try {
            const cacheData = JSON.parse(cached);

            // Check if hash matches (structure unchanged)
            if (cacheData.hash !== data.structure_hash) {
                console.log('Structure changed, clearing duration cache');
                localStorage.removeItem(cacheKey);
                return false;
            }

            // Apply cached durations
            const durations = cacheData.durations;
            this.applyDurations(data, durations);
            console.log('Loaded durations from cache');
            return true;

        } catch (e) {
            console.error('Failed to load cached durations:', e);
            localStorage.removeItem(cacheKey);
            return false;
        }
    },

    /**
     * Apply durations map to playlist data
     */
    applyDurations(data, durations) {
        // Apply to root videos
        for (const video of data.videos || []) {
            if (durations[video.path]) {
                video.duration = durations[video.path];
            }
        }

        // Apply to chapter videos (recursive)
        const processChapter = (chapter) => {
            let chapterDuration = 0;
            for (const video of chapter.videos || []) {
                if (durations[video.path]) {
                    video.duration = durations[video.path];
                }
                chapterDuration += video.duration || 0;
            }
            for (const child of chapter.children || []) {
                chapterDuration += processChapter(child);
            }
            chapter.duration = chapterDuration;
            return chapterDuration;
        };

        let totalDuration = 0;
        for (const video of data.videos || []) {
            totalDuration += video.duration || 0;
        }
        for (const chapter of data.chapters || []) {
            totalDuration += processChapter(chapter);
        }
        data.total_duration = totalDuration;
    },

    /**
     * Save durations to localStorage cache
     */
    saveDurationsCache(durations) {
        if (!this.state.playlist) return;

        const cacheKey = this.DURATION_CACHE_PREFIX + this.state.playlist.root_path;
        const cacheData = {
            hash: this.state.playlist.structure_hash,
            durations: durations,
            timestamp: Date.now()
        };

        try {
            localStorage.setItem(cacheKey, JSON.stringify(cacheData));
        } catch (e) {
            console.error('Failed to save duration cache:', e);
        }
    },

    /**
     * Check if durations need to be calculated and start background calculation
     */
    checkAndCalculateDurations() {
        if (!this.state.playlist) return;

        // Check if we have all durations
        const allVideos = Playlist.allVideos;
        const missingDurations = allVideos.filter(v => !v.duration || v.duration === 0);

        if (missingDurations.length === 0) {
            console.log('All durations already loaded');
            return;
        }

        console.log(`Need to calculate ${missingDurations.length} durations`);
        this.calculateDurationsInBackground(missingDurations);
    },

    /**
     * Calculate durations in background, one at a time
     */
    async calculateDurationsInBackground(videos) {
        this.state.isCalculatingDurations = true;
        this.state.durationProgress = { current: 0, total: videos.length };

        // Show calculating indicator
        this.updateDurationIndicator();

        const durations = {};

        // First, collect any existing durations
        for (const video of Playlist.allVideos) {
            if (video.duration > 0) {
                durations[video.path] = video.duration;
            }
        }

        // Calculate missing durations one by one
        for (let i = 0; i < videos.length; i++) {
            const video = videos[i];
            this.state.durationProgress.current = i + 1;
            this.updateDurationIndicator();

            try {
                const response = await fetch('/api/duration', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: video.path })
                });

                if (response.ok) {
                    const result = await response.json();
                    video.duration = result.duration;
                    durations[video.path] = result.duration;

                    // Update total duration incrementally
                    this.recalculateTotalDuration();
                    this.updateStats();
                }
            } catch (e) {
                console.error(`Failed to get duration for ${video.path}:`, e);
            }
        }

        // Save to cache
        this.saveDurationsCache(durations);

        this.state.isCalculatingDurations = false;
        this.updateStats();
        Playlist.render(); // Re-render to show durations

        console.log('Duration calculation complete');
    },

    /**
     * Recalculate total duration from all videos
     */
    recalculateTotalDuration() {
        if (!this.state.playlist) return;

        let total = 0;
        for (const video of Playlist.allVideos) {
            total += video.duration || 0;
        }
        this.state.playlist.total_duration = total;
    },

    /**
     * Update the duration indicator in the stats bar
     */
    updateDurationIndicator() {
        const durationEl = this.statDuration.querySelector('.stat-value');

        if (this.state.isCalculatingDurations) {
            const { current, total } = this.state.durationProgress;
            const currentDuration = this.formatDuration(this.state.playlist?.total_duration || 0);
            durationEl.innerHTML = `${currentDuration} <span class="calculating-indicator">(${current}/${total})</span>`;
        } else {
            durationEl.textContent = this.formatDuration(this.state.playlist?.total_duration || 0);
        }
    },

    /**
     * Update course statistics
     */
    updateStats() {
        if (!this.state.playlist) return;

        const totalVideos = this.state.playlist.total_videos;
        const completionPercent = Progress.calculateCompletion(Playlist.allVideos);

        this.statVideos.querySelector('.stat-value').textContent = totalVideos;
        this.statProgress.querySelector('.stat-value').textContent = `${completionPercent}%`;

        // Duration is updated via updateDurationIndicator
        this.updateDurationIndicator();
    },

    /**
     * Resume last watched video or start from beginning
     */
    resumeLastVideo() {
        if (!this.state.playlist) return;

        const lastWatched = Progress.getLastWatched(this.state.playlist.root_path);

        if (lastWatched) {
            const video = Playlist.getVideoByPath(lastWatched);
            if (video) {
                this.playVideo(video);
                return;
            }
        }

        // Play first video
        if (Playlist.allVideos.length > 0) {
            this.playVideo(Playlist.allVideos[0]);
        }
    },

    /**
     * Play a video
     * @param {Object} video - Video object
     */
    playVideo(video) {
        if (!video) return;

        this.state.currentVideo = video;

        // Load in player
        Player.load(video);

        // Update playlist highlighting
        Playlist.setActiveVideo(video);
        Playlist.expandToVideo(video);

        // Show chapter documents
        if (video.chapterObj) {
            this.showDocuments(video.chapterObj.documents);
        } else {
            this.showDocuments(this.state.playlist?.documents);
        }
    },

    /**
     * Show documents in the right panel
     * @param {Array} documents - Array of document objects
     */
    showDocuments(documents) {
        if (!documents || documents.length === 0) {
            this.documentsList.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon">📄</div>
                    <div class="empty-text">No documents in this section</div>
                </div>
            `;
            this.docCount.textContent = '0';
            return;
        }

        this.docCount.textContent = documents.length;

        let html = '';
        for (const doc of documents) {
            const icon = this.getDocumentIcon(doc.type);
            html += `
                <div class="document-item" data-doc-path="${this.escapeHtml(doc.path)}"
                     data-doc-type="${doc.type}"
                     data-doc-title="${this.escapeHtml(doc.title)}"
                     data-doc-file="${this.escapeHtml(doc.file)}">
                    <span class="doc-icon">${icon}</span>
                    <div class="doc-info">
                        <div class="doc-name">${this.escapeHtml(doc.title)}</div>
                        <div class="doc-type">${doc.type}</div>
                    </div>
                </div>
            `;
        }

        this.documentsList.innerHTML = html;

        // Attach click handlers
        this.documentsList.querySelectorAll('.document-item').forEach(item => {
            item.addEventListener('click', () => {
                Modal.open({
                    type: item.dataset.docType,
                    title: item.dataset.docTitle,
                    path: item.dataset.docPath,
                    file: item.dataset.docFile
                });
            });
        });
    },

    /**
     * Get icon for document type
     * @param {string} type - Document type
     * @returns {string} - Emoji icon
     */
    getDocumentIcon(type) {
        const icons = {
            'pdf': '📕',
            'image': '🖼️',
            'text': '📝',
            'json': '📋',
            'zip': '📦',
            'other': '📄'
        };
        return icons[type] || '📄';
    },

    /**
     * Initialize sidebar resize functionality
     */
    initSidebarResize() {
        const sidebar = document.getElementById('sidebar');
        const resizeHandle = document.getElementById('sidebar-resize');

        if (!sidebar || !resizeHandle) return;

        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        resizeHandle.addEventListener('mousedown', (e) => {
            isResizing = true;
            startX = e.clientX;
            startWidth = sidebar.offsetWidth;
            resizeHandle.classList.add('dragging');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';
            e.preventDefault();
        });

        document.addEventListener('mousemove', (e) => {
            if (!isResizing) return;

            const diff = e.clientX - startX;
            const newWidth = Math.min(Math.max(startWidth + diff, 200), 500);
            sidebar.style.width = `${newWidth}px`;
        });

        document.addEventListener('mouseup', () => {
            if (isResizing) {
                isResizing = false;
                resizeHandle.classList.remove('dragging');
                document.body.style.cursor = '';
                document.body.style.userSelect = '';

                // Save width preference
                localStorage.setItem('video_player:sidebar_width', sidebar.offsetWidth);
            }
        });

        // Restore saved width
        const savedWidth = localStorage.getItem('video_player:sidebar_width');
        if (savedWidth) {
            sidebar.style.width = `${savedWidth}px`;
        }
    },

    /**
     * Show loading overlay
     */
    showLoading() {
        this.loadingOverlay.classList.remove('hidden');
    },

    /**
     * Hide loading overlay
     */
    hideLoading() {
        this.loadingOverlay.classList.add('hidden');
    },

    /**
     * Show toast notification
     * @param {string} message - Message to show
     * @param {string} type - Toast type (success, error, info)
     */
    showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;

        this.toastContainer.appendChild(toast);

        // Trigger animation
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // Remove after delay
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => {
                toast.remove();
            }, 350);
        }, 3000);
    },

    /**
     * Format duration in seconds to human readable
     * @param {number} seconds - Duration in seconds
     * @returns {string} - Formatted duration
     */
    formatDuration(seconds) {
        if (!seconds || seconds === 0) return '0:00';

        const hours = Math.floor(seconds / 3600);
        const mins = Math.floor((seconds % 3600) / 60);

        if (hours > 0) {
            return `${hours}h ${mins}m`;
        }
        return `${mins}m`;
    },

    /**
     * Escape HTML special characters
     * @param {string} text - Raw text
     * @returns {string} - Escaped text
     */
    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export for use in other modules
window.App = App;
