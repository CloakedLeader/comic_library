if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('service-worker.js')
    .then(() => console.log('Service Worker Registered'))
    .catch(err => console.error('Service Worker registration failed:', err))
}

document.addEventListener('DOMContentLoaded', () => {
    const list = document.getElementById('file_list');
    
    fetch('/files')
        .then(res => res.json())
        .then(files => {
            files.forEach(file => {
                const li = document.createElement('li');
                li.textContent = file;
                list.appendChild(li);
            });
        });
});
