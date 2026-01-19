/**
 * Progress tracking module
 * Handles localStorage persistence for video progress and completion
 */

const Progress = {
    // Storage keys prefix
    PREFIX: 'video_player:',

    /**
     * Get the progress (current time) for a video
     * @param {string} videoPath - Video path
     * @returns {number} - Seconds watched (0 if not found)
     */
    getVideoProgress(videoPath) {
        const key = this.PREFIX + 'progress:' + videoPath;
        const value = localStorage.getItem(key);
        return value ? parseFloat(value) : 0;
    },

    /**
     * Save progress for a video
     * @param {string} videoPath - Video path
     * @param {number} currentTime - Current playback position in seconds
     */
    saveVideoProgress(videoPath, currentTime) {
        const key = this.PREFIX + 'progress:' + videoPath;
        localStorage.setItem(key, currentTime.toString());
    },

    /**
     * Check if a video is marked as completed
     * @param {string} videoPath - Video path
     * @returns {boolean}
     */
    isVideoCompleted(videoPath) {
        const key = this.PREFIX + 'completed:' + videoPath;
        return localStorage.getItem(key) === 'true';
    },

    /**
     * Mark a video as completed
     * @param {string} videoPath - Video path
     */
    markVideoCompleted(videoPath) {
        const key = this.PREFIX + 'completed:' + videoPath;
        localStorage.setItem(key, 'true');
    },

    /**
     * Unmark a video as completed
     * @param {string} videoPath - Video path
     */
    unmarkVideoCompleted(videoPath) {
        const key = this.PREFIX + 'completed:' + videoPath;
        localStorage.removeItem(key);
    },

    /**
     * Get all completed videos for a course
     * @param {string} courseRoot - Course root path
     * @returns {Set<string>} - Set of completed video paths
     */
    getCompletedVideos(courseRoot) {
        const completed = new Set();
        const prefix = this.PREFIX + 'completed:';

        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(prefix)) {
                const videoPath = key.substring(prefix.length);
                if (localStorage.getItem(key) === 'true') {
                    completed.add(videoPath);
                }
            }
        }

        return completed;
    },

    /**
     * Calculate completion percentage for a list of videos
     * @param {Array} videos - Array of video objects with 'path' property
     * @returns {number} - Percentage (0-100)
     */
    calculateCompletion(videos) {
        if (!videos || videos.length === 0) return 0;

        let completed = 0;
        for (const video of videos) {
            if (this.isVideoCompleted(video.path)) {
                completed++;
            }
        }

        return Math.round((completed / videos.length) * 100);
    },

    /**
     * Get the last watched video path for a course
     * @param {string} courseRoot - Course root path
     * @returns {string|null} - Video path or null
     */
    getLastWatched(courseRoot) {
        const key = this.PREFIX + 'last_watched:' + courseRoot;
        return localStorage.getItem(key);
    },

    /**
     * Save the last watched video for a course
     * @param {string} courseRoot - Course root path
     * @param {string} videoPath - Video path
     */
    saveLastWatched(courseRoot, videoPath) {
        const key = this.PREFIX + 'last_watched:' + courseRoot;
        localStorage.setItem(key, videoPath);
    },

    /**
     * Get custom playlist order (from drag & drop)
     * @param {string} courseRoot - Course root path
     * @returns {Object|null} - Custom order object or null
     */
    getCustomOrder(courseRoot) {
        const key = this.PREFIX + 'custom_order:' + courseRoot;
        const value = localStorage.getItem(key);
        if (value) {
            try {
                return JSON.parse(value);
            } catch (e) {
                return null;
            }
        }
        return null;
    },

    /**
     * Save custom playlist order
     * @param {string} courseRoot - Course root path
     * @param {Object} order - Order object
     */
    saveCustomOrder(courseRoot, order) {
        const key = this.PREFIX + 'custom_order:' + courseRoot;
        localStorage.setItem(key, JSON.stringify(order));
    },

    /**
     * Clear all progress for a course
     * @param {string} courseRoot - Course root path (optional, clears all if not provided)
     */
    clearProgress(courseRoot = null) {
        const keysToRemove = [];

        for (let i = 0; i < localStorage.length; i++) {
            const key = localStorage.key(i);
            if (key && key.startsWith(this.PREFIX)) {
                if (courseRoot === null || key.includes(courseRoot)) {
                    keysToRemove.push(key);
                }
            }
        }

        for (const key of keysToRemove) {
            localStorage.removeItem(key);
        }
    },

    /**
     * Get playback speed preference
     * @returns {number} - Playback rate (default 1)
     */
    getPlaybackSpeed() {
        const value = localStorage.getItem(this.PREFIX + 'playback_speed');
        return value ? parseFloat(value) : 1;
    },

    /**
     * Save playback speed preference
     * @param {number} speed - Playback rate
     */
    savePlaybackSpeed(speed) {
        localStorage.setItem(this.PREFIX + 'playback_speed', speed.toString());
    },

    /**
     * Get autoplay preference
     * @returns {boolean} - Autoplay enabled (default true)
     */
    getAutoplay() {
        const value = localStorage.getItem(this.PREFIX + 'autoplay');
        return value !== 'false';
    },

    /**
     * Save autoplay preference
     * @param {boolean} enabled - Autoplay enabled
     */
    saveAutoplay(enabled) {
        localStorage.setItem(this.PREFIX + 'autoplay', enabled.toString());
    }
};

// Export for use in other modules
window.Progress = Progress;
