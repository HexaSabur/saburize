document.addEventListener('DOMContentLoaded', () => {
    const timerDisplay = document.getElementById('timerDisplay');
    const modeIndicator = document.getElementById('modeIndicator');
    const startBtn = document.getElementById('startBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    const resetBtn = document.getElementById('resetBtn');

    const WORK_TIME = 25 * 60; // 25 minutes in seconds
    const BREAK_TIME = 5 * 60; // 5 minutes in seconds

    let timeLeft = WORK_TIME;
    let timerId = null;
    let isWorkMode = true;

    function updateDisplay() {
        const minutes = Math.floor(timeLeft / 60);
        const seconds = timeLeft % 60;
        
        const formattedMinutes = minutes.toString().padStart(2, '0');
        const formattedSeconds = seconds.toString().padStart(2, '0');
        
        const timeString = `${formattedMinutes}:${formattedSeconds}`;
        timerDisplay.textContent = timeString;
        document.title = `${timeString} - Pomodoro`;
    }

    function switchMode() {
        isWorkMode = !isWorkMode;
        timeLeft = isWorkMode ? WORK_TIME : BREAK_TIME;
        
        modeIndicator.textContent = isWorkMode ? 'Çalışma Süresi' : 'Mola Süresi';
        
        if (isWorkMode) {
            modeIndicator.classList.remove('break');
        } else {
            modeIndicator.classList.add('break');
        }
        
        updateDisplay();
    }

    function startTimer() {
        if (timerId !== null) return; // Already running

        timerId = setInterval(() => {
            timeLeft--;
            updateDisplay();

            if (timeLeft <= 0) {
                clearInterval(timerId);
                timerId = null;
                switchMode();
                startTimer(); // Auto-start next mode
            }
        }, 1000);
    }

    function pauseTimer() {
        if (timerId !== null) {
            clearInterval(timerId);
            timerId = null;
        }
    }

    function resetTimer() {
        pauseTimer();
        isWorkMode = true;
        timeLeft = WORK_TIME;
        
        modeIndicator.textContent = 'Çalışma Süresi';
        modeIndicator.classList.remove('break');
        
        updateDisplay();
    }

    startBtn.addEventListener('click', startTimer);
    pauseBtn.addEventListener('click', pauseTimer);
    resetBtn.addEventListener('click', resetTimer);

    // Initial display
    updateDisplay();
});
