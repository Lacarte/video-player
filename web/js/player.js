/**
 * Video Player module
 * Handles video playback, controls, subtitles, and progress saving
 */

const Player = {
    // DOM elements
    video: null,
    container: null,
    overlay: null,
    nowPlayingTitle: null,
    speedSelect: null,
    subtitleSelect: null,
    subtitleGroup: null,
    autoplayToggle: null,
    btnPrev: null,
    btnNext: null,

    // State
    currentVideo: null,
    saveProgressInterval: null,
    completionThreshold: 0.9,  // Mark complete at 90%

    /**
     * Initialize player module
     */
    init() {
        this.video = document.getElementById('video-player');
        this.container = document.getElementById('video-container');
        this.overlay = document.getElementById('video-overlay');
        this.nowPlayingTitle = document.getElementById('now-playing-title');
        this.speedSelect = document.getElementById('speed-select');
        this.subtitleSelect = document.getElementById('subtitle-select');
        this.subtitleGroup = document.getElementById('subtitle-group');
        this.autoplayToggle = document.getElementById('autoplay-toggle');
        this.btnPrev = document.getElementById('btn-prev');
        this.btnNext = document.getElementById('btn-next');

        this.attachEventListeners();
        this.loadPreferences();
    },

    /**
     * Attach event listeners
     */
    attachEventListeners() {
        // Video events
        this.video.addEventListener('loadedmetadata', () => this.onVideoLoaded());
        this.video.addEventListener('timeupdate', () => this.onTimeUpdate());
        this.video.addEventListener('ended', () => this.onVideoEnded());
        this.video.addEventListener('play', () => this.onPlay());
        this.video.addEventListener('pause', () => this.onPause());
        this.video.addEventListener('error', (e) => this.onError(e));

        // Controls
        this.speedSelect.addEventListener('change', () => this.onSpeedChange());
        this.subtitleSelect.addEventListener('change', () => this.onSubtitleChange());
        this.autoplayToggle.addEventListener('change', () => this.onAutoplayChange());
        this.btnPrev.addEventListener('click', () => this.playPrevious());
        this.btnNext.addEventListener('click', () => this.playNext());

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => this.handleKeyboard(e));
    },

    /**
     * Load user preferences
     */
    loadPreferences() {
        // Playback speed
        const speed = Progress.getPlaybackSpeed();
        this.speedSelect.value = speed;
        this.video.playbackRate = speed;

        // Autoplay
        const autoplay = Progress.getAutoplay();
        this.autoplayToggle.checked = autoplay;
    },

    /**
     * Load and play a video
     * @param {Object} video - Video object
     */
    load(video) {
        if (!video) return;

        this.currentVideo = video;

        // Clear existing subtitles
        this.clearSubtitles();

        // Set video source
        this.video.src = video.path;

        // Update UI
        this.nowPlayingTitle.textContent = video.title;
        this.overlay.classList.add('hidden');

        // Load subtitles if available
        if (video.subtitles && video.subtitles.length > 0) {
            this.loadSubtitles(video.subtitles);
        } else {
            this.subtitleGroup.style.display = 'none';
        }

        // Restore progress after metadata loads
        const savedProgress = Progress.getVideoProgress(video.path);
        if (savedProgress > 0) {
            // Set currentTime after metadata is loaded for better seeking
            const onCanPlay = () => {
                this.video.currentTime = savedProgress;
                this.video.removeEventListener('canplay', onCanPlay);
            };
            this.video.addEventListener('canplay', onCanPlay);
        }

        // Start playing (setting src already triggers load with preload="metadata")
        this.video.play().catch(e => {
            console.log('Autoplay prevented:', e);
        });

        // Update navigation buttons
        this.updateNavButtons();
    },

    /**
     * Clear all subtitle tracks
     */
    clearSubtitles() {
        // Remove existing tracks
        while (this.video.firstChild) {
            if (this.video.firstChild.tagName === 'TRACK') {
                this.video.removeChild(this.video.firstChild);
            } else {
                break;
            }
        }

        // Reset select
        this.subtitleSelect.innerHTML = '<option value="">Off</option>';
    },

    /**
     * Load subtitles for current video
     * @param {Array} subtitles - Array of subtitle objects
     */
    loadSubtitles(subtitles) {
        this.subtitleGroup.style.display = 'flex';
        this.subtitleSelect.innerHTML = '<option value="">Off</option>';

        for (let i = 0; i < subtitles.length; i++) {
            const sub = subtitles[i];

            // Add track to video
            const track = document.createElement('track');
            track.kind = 'subtitles';
            track.label = sub.label;
            track.srclang = sub.lang;
            track.src = sub.path;
            if (i === 0) {
                track.default = true;
            }
            this.video.appendChild(track);

            // Add option to select
            const option = document.createElement('option');
            option.value = i.toString();
            option.textContent = sub.label;
            this.subtitleSelect.appendChild(option);
        }

        // Enable first subtitle by default if only one
        if (subtitles.length === 1) {
            this.subtitleSelect.value = '0';
            this.enableSubtitle(0);
        }
    },

    /**
     * Enable a subtitle track
     * @param {number} index - Track index (-1 for off)
     */
    enableSubtitle(index) {
        const tracks = this.video.textTracks;
        for (let i = 0; i < tracks.length; i++) {
            tracks[i].mode = (i === index) ? 'showing' : 'hidden';
        }
    },

    /**
     * Handle video loaded event
     */
    onVideoLoaded() {
        // Apply playback speed
        this.video.playbackRate = parseFloat(this.speedSelect.value);

        // Start progress saving
        this.startProgressSaving();
    },

    /**
     * Handle time update event
     */
    onTimeUpdate() {
        if (!this.currentVideo) return;

        // Check for completion
        const duration = this.video.duration;
        const currentTime = this.video.currentTime;

        if (duration > 0 && (currentTime / duration) >= this.completionThreshold) {
            if (!Progress.isVideoCompleted(this.currentVideo.path)) {
                Progress.markVideoCompleted(this.currentVideo.path);
                Playlist.markVideoCompleted(this.currentVideo.path);
                App.updateStats();
                App.showToast('Video marked as completed', 'success');
            }
        }
    },

    /**
     * Handle video ended event
     */
    onVideoEnded() {
        // Save final progress
        this.saveProgress();

        // Mark as completed
        if (this.currentVideo && !Progress.isVideoCompleted(this.currentVideo.path)) {
            Progress.markVideoCompleted(this.currentVideo.path);
            Playlist.markVideoCompleted(this.currentVideo.path);
            App.updateStats();
        }

        // Auto-play next if enabled
        if (this.autoplayToggle.checked) {
            this.playNext();
        }
    },

    /**
     * Handle play event
     */
    onPlay() {
        this.startProgressSaving();
    },

    /**
     * Handle pause event
     */
    onPause() {
        this.saveProgress();
    },

    /**
     * Handle video error
     * @param {Event} e - Error event
     */
    onError(e) {
        console.error('Video error:', e);
        this.overlay.classList.remove('hidden');
        this.overlay.querySelector('.overlay-text').textContent = 'Error loading video';
        App.showToast('Failed to load video', 'error');
    },

    /**
     * Handle speed change
     */
    onSpeedChange() {
        const speed = parseFloat(this.speedSelect.value);
        this.video.playbackRate = speed;
        Progress.savePlaybackSpeed(speed);
    },

    /**
     * Handle subtitle change
     */
    onSubtitleChange() {
        const value = this.subtitleSelect.value;
        if (value === '') {
            this.enableSubtitle(-1);
        } else {
            this.enableSubtitle(parseInt(value));
        }
    },

    /**
     * Handle autoplay change
     */
    onAutoplayChange() {
        Progress.saveAutoplay(this.autoplayToggle.checked);
    },

    /**
     * Start periodic progress saving
     */
    startProgressSaving() {
        this.stopProgressSaving();
        this.saveProgressInterval = setInterval(() => {
            this.saveProgress();
        }, 5000);  // Save every 5 seconds
    },

    /**
     * Stop periodic progress saving
     */
    stopProgressSaving() {
        if (this.saveProgressInterval) {
            clearInterval(this.saveProgressInterval);
            this.saveProgressInterval = null;
        }
    },

    /**
     * Save current progress
     */
    saveProgress() {
        if (!this.currentVideo) return;
        if (this.video.currentTime > 0) {
            Progress.saveVideoProgress(this.currentVideo.path, this.video.currentTime);
            Progress.saveLastWatched(App.state.playlist?.root_path, this.currentVideo.path);
        }
    },

    /**
     * Play next video
     */
    playNext() {
        const next = Playlist.getNextVideo(this.currentVideo);
        if (next) {
            App.playVideo(next);
        } else {
            App.showToast('End of playlist', 'info');
        }
    },

    /**
     * Play previous video
     */
    playPrevious() {
        const prev = Playlist.getPreviousVideo(this.currentVideo);
        if (prev) {
            App.playVideo(prev);
        } else {
            App.showToast('Beginning of playlist', 'info');
        }
    },

    /**
     * Update navigation button states
     */
    updateNavButtons() {
        const hasPrev = Playlist.getPreviousVideo(this.currentVideo) !== null;
        const hasNext = Playlist.getNextVideo(this.currentVideo) !== null;

        this.btnPrev.disabled = !hasPrev;
        this.btnNext.disabled = !hasNext;
    },

    /**
     * Handle keyboard shortcuts
     * @param {KeyboardEvent} e - Keyboard event
     */
    handleKeyboard(e) {
        // Ignore if typing in input
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT') {
            return;
        }

        switch (e.key) {
            case ' ':
                e.preventDefault();
                if (this.video.paused) {
                    this.video.play();
                } else {
                    this.video.pause();
                }
                break;

            case 'ArrowLeft':
                e.preventDefault();
                this.video.currentTime = Math.max(0, this.video.currentTime - 10);
                break;

            case 'ArrowRight':
                e.preventDefault();
                this.video.currentTime = Math.min(this.video.duration, this.video.currentTime + 10);
                break;

            case 'ArrowUp':
                e.preventDefault();
                this.video.volume = Math.min(1, this.video.volume + 0.1);
                break;

            case 'ArrowDown':
                e.preventDefault();
                this.video.volume = Math.max(0, this.video.volume - 0.1);
                break;

            case 'N':
            case 'n':
                if (e.shiftKey) {
                    e.preventDefault();
                    this.playNext();
                }
                break;

            case 'P':
            case 'p':
                if (e.shiftKey) {
                    e.preventDefault();
                    this.playPrevious();
                }
                break;

            case 'f':
            case 'F':
                e.preventDefault();
                if (document.fullscreenElement) {
                    document.exitFullscreen();
                } else {
                    this.container.requestFullscreen();
                }
                break;

            case 'm':
            case 'M':
                e.preventDefault();
                this.video.muted = !this.video.muted;
                break;
        }
    },

    /**
     * Cleanup on unload
     */
    cleanup() {
        this.stopProgressSaving();
        this.saveProgress();
    }
};

// Save progress before page unload
window.addEventListener('beforeunload', () => {
    Player.cleanup();
});

// Export for use in other modules
window.Player = Player;
