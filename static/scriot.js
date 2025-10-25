alert("Some Guideance:-\n\n👉1. If you get time out message try to change the new channel name.\n👉2. DRefresh the page after every search query then searcht again.\n👉3. Wish you the best experience possible!")
const statusEl = document.getElementById('status');
const btn = document.getElementById('scrape-btn');
const input = document.getElementById('outlet-input');
const tbody = document.querySelector('#authors-table tbody');
let beatsChart = null;
let network = null;
let demoRendered = false;

// Create loader element and styles
const loader = document.createElement('div');
loader.id = 'loader';
loader.style.display = 'none';
loader.style.position = 'fixed';
loader.style.top = '50%';
loader.style.left = '50%';
loader.style.transform = 'translate(-50%, -50%)';
loader.style.border = '8px solid #f3f3f3';
loader.style.borderTop = '8px solid #3498db';
loader.style.borderRadius = '50%';
loader.style.width = '60px';
loader.style.height = '60px';
loader.style.animation = 'spin 1s linear infinite';
document.body.appendChild(loader);

const style = document.createElement('style');
style.type = 'text/css';
style.innerHTML = `
@keyframes spin {
    0% { transform: translate(-50%, -50%) rotate(0deg); }
    100% { transform: translate(-50%, -50%) rotate(360deg); }
}`;
document.head.appendChild(style);

btn.addEventListener('click', async () => {
    const outlet = input.value.trim();
    if(!outlet){
        statusEl.textContent = 'Enter outlet name';
        return;
    }
    statusEl.textContent = 'Scraping...';
    loader.style.display = 'block';

    try {
        console.log('Sending POST request to backend for outlet:', outlet);
        const resp = await fetch('http://127.0.0.1:5000/api/scrape', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ outlet })
        });
        if(!resp.ok){ throw new Error(`HTTP error! Status: ${resp.status}`); }
        const data = await resp.json();
        console.log('Data received:', data);
        if(!data || data.length === 0){
            statusEl.textContent = 'No profiles found for this outlet';
            alert('Time out Try Again!');
            loader.style.display = 'none';
            return;
        }
        statusEl.textContent = `Loaded ${data.length} profiles`;
        renderTable(data);
        renderBeats(data);
        renderNetwork(data);
        loader.style.display = 'none';
    } catch (e) {
        console.error('Error fetching from backend:', e);
        statusEl.textContent = 'Error fetching data from backend, using demo data';
        loader.style.display = 'none';
        renderDemoData();
    }
});

function renderTable(data){
    tbody.innerHTML = '';
    data.forEach(j => {
        const tr = document.createElement('tr');
        tr.innerHTML = `<td>${escapeHtml(j.name)}</td><td>${escapeHtml(j.beat || 'Unknown')}</td><td>${escapeHtml(j.latest_article || '—')}</td><td>${j.articles_count || 0}</td>`;
        tbody.appendChild(tr);
    });
}

function renderBeats(data){
    const counts = {};
    data.forEach(d => { const b = d.beat || 'Unknown'; counts[b] = (counts[b] || 0) + 1; });
    const labels = Object.keys(counts);
    const values = labels.map(l => counts[l]);
    const canvas = document.getElementById('beatsChart');
    canvas.height = 300; // fixed height
    canvas.width = 500;  // fixed width
    const ctx = canvas.getContext('2d');
    if(beatsChart){ beatsChart.destroy(); beatsChart = null; }
    beatsChart = new Chart(ctx, {
        type: 'bar',
        data: { labels, datasets: [{ label: 'Profiles by beat', data: values, backgroundColor: '#6ee7b7' }] },
        options: {
            responsive: false,
            maintainAspectRatio: false,
            animation: { duration: 0 },
            plugins: { legend: { display: true } },
            scales: { y: { beginAtZero: true } }
        }
    });
}

function renderNetwork(data){
    const nodes = [], edges = [], beatIndex = {};
    let nid = 1;
    data.forEach(j => {
        nodes.push({ id: nid, label: j.name, group: 'journalist' });
        const jId = nid; nid++;
        const beat = j.beat || 'Unknown';
        if(!beatIndex[beat]){ beatIndex[beat] = nid; nodes.push({ id: nid, label: beat, group: 'beat' }); nid++; }
        edges.push({ from: jId, to: beatIndex[beat] });
    });
    const container = document.getElementById('network');
    const dataVis = { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) };
    const options = { nodes: { shape: 'dot', size: 12 }, physics: { stabilization: true } };
    if(network){ network.destroy(); network = null; }
    network = new vis.Network(container, dataVis, options);
}

function renderDemoData(){
    if(demoRendered) return;
    demoRendered = true;
    console.log('Rendering demo data');
    const data = [];
    const beats = ['Politics','Business','Sports','Technology','Culture','Science','Opinion','Health','Environment'];
    for(let i=0;i<30;i++){
        data.push({
            name: `Journalist ${i+1}`,
            beat: beats[i % beats.length],
            latest_article: `${beats[i % beats.length]} Article ${i+1}`,
            articles_count: Math.floor(Math.random()*100)
        });
    }
    renderTable(data);
    renderBeats(data);
    renderNetwork(data);
}

function escapeHtml(str){ return String(str).replace(/[&<>\\"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;','\\' :'&#39;'}[s])); }

window.addEventListener('load', ()=>{ input.value='Sample Outlet'; renderDemoData(); });