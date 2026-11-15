export default function({parentElement, data, setTriggerValue}) {
    const canvas = parentElement.querySelector("canvas");
    const pins = parentElement.querySelector(".pins");
    canvas.orbitwatchCleanup?.();
    const ctx = canvas.getContext("2d");
    const rad = Math.PI / 180, size = canvas.width, mid = size / 2;
    const frame = ctx.createImageData(size, size);
    const image = new Image();
    const selected = data.pins.find(p => p.id === data.selected) ?? data.pins[0];
    const signature = JSON.stringify(data.pins.map(({id, lat, lon}) => [id, lat, lon]));
    const savedView = canvas.orbitwatchView;
    const view = savedView?.signature === signature ? savedView : {
        signature,
        lat: Math.max(-75, Math.min(75, selected.lat - 11)) * rad,
        lon: selected.lon * rad,
        zoom: 1,
    };
    canvas.orbitwatchView = view;
    let {lat, lon, zoom} = view;
    let texture, drag, pending = 0;
    const controls = data.pins.map(pin => {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = pin.icon;
        button.title = pin.name;
        button.setAttribute("aria-label", pin.name);
        button.setAttribute("aria-pressed", String(pin.id === data.selected));
        button.onclick = () => { if (pin.id !== "custom") setTriggerValue("marker", pin.id); };
        if (pin.id === "custom") { button.disabled = true; button.tabIndex = -1; }
        return button;
    });

    pins.replaceChildren(...controls);

    function draw() {
        pending = 0;
        Object.assign(view, {lat, lon, zoom});
        const radius = mid * .87 * zoom, sin = Math.sin(lat), cos = Math.cos(lat);
        const pixels = frame.data;
        for (let y = 0; y < size; y++) {
            const v = (mid-y)/radius;
            for (let x = 0; x < size; x++) {
                const u = (x-mid)/radius, d = u*u+v*v, i = (y*size+x)*4;
                if (d > 1) {
                    pixels[i]=19; pixels[i+1]=144; pixels[i+2]=255;
                    pixels[i+3]=Math.round(105*Math.exp(-(d-1)*27));
                    continue;
                }
                const z = Math.sqrt(1-d), shade = .62+.42*Math.max(0,z-u*.3+v*.2);
                const rim = Math.pow(d, 11);
                if (texture) {
                    const phi = Math.asin(Math.max(-1,Math.min(1,v*cos+z*sin)));
                    const theta = lon + Math.atan2(u,z*cos-v*sin);
                    const tx = Math.floor((((theta/(2*Math.PI)+.5)%1+1)%1)*texture.width);
                    const ty = Math.min(texture.height-1,Math.max(0,Math.floor((.5-phi/Math.PI)*texture.height)));
                    const j = (ty*texture.width+tx)*4;
                    pixels[i]=texture.data[j]*shade+rim*34;
                    pixels[i+1]=texture.data[j+1]*shade+rim*110;
                    pixels[i+2]=texture.data[j+2]*shade+rim*191;
                } else {
                    pixels[i]=10+rim*40; pixels[i+1]=40+rim*110; pixels[i+2]=72+rim*180;
                }
                pixels[i+3]=255;
            }
        }
        ctx.putImageData(frame,0,0);
        const width = canvas.clientWidth;
        const placed = [];
        const gap = 32;
        const points = data.pins.map((pin, i) => {
            const p = pin.lat * rad, delta = pin.lon * rad - lon;
            const x = Math.cos(p) * Math.sin(delta);
            const y = Math.sin(p) * cos - Math.cos(p) * Math.cos(delta) * sin;
            const z = Math.sin(p) * sin + Math.cos(p) * Math.cos(delta) * cos;
            return {i, z, x: (mid + x * radius) * width / size, y: (mid - y * radius) * width / size};
        });
        for (const {i, x, y, z} of points) {
            const button = controls[i];
            button.hidden = z <= 0 || x < 0 || x > width || y < 0 || y > width;
            if (button.hidden) continue;
            const clamp = n => Math.max(15, Math.min(width - 15, n));
            let bx = clamp(x), by = clamp(y);
            for (let ring = 1; ring <= 4 && placed.some(([px, py]) => Math.hypot(px - bx, py - by) < gap); ring++) {
                for (let step = 0; step < 8; step++) {
                    const angle = step * Math.PI / 4;
                    const nx = clamp(x + gap * ring * Math.cos(angle));
                    const ny = clamp(y + gap * ring * Math.sin(angle));
                    if (placed.every(([px, py]) => Math.hypot(px - nx, py - ny) >= gap)) {
                        bx = nx;
                        by = ny;
                        break;
                    }
                }
            }
            placed.push([bx, by]);
            button.style.left = bx + "px";
            button.style.top = by + "px";
            if (Math.hypot(bx - x, by - y) > 2 && width) {
                ctx.strokeStyle = "#72eaff";
                ctx.beginPath();
                ctx.moveTo(x * size / width, y * size / width);
                ctx.lineTo(bx * size / width, by * size / width);
                ctx.stroke();
            }
        }
    }
    const redraw = () => { if (!pending) pending = requestAnimationFrame(draw); };
    image.onload = () => {
        const map = document.createElement("canvas");
        map.width=image.width; map.height=image.height;
        const c=map.getContext("2d");
        c.drawImage(image,0,0);
        texture=c.getImageData(0,0,map.width,map.height);
        redraw();
    };
    if (data.texture) image.src=data.texture;
    canvas.onpointerdown = e => {
        drag=[e.clientX,e.clientY];
        canvas.setPointerCapture(e.pointerId);
    };
    canvas.onpointermove = e => {
        if (!drag) return;
        const scale=3/(canvas.clientWidth*zoom);
        lon -= (e.clientX-drag[0])*scale;
        lat = Math.max(-Math.PI/2,Math.min(Math.PI/2,lat+(e.clientY-drag[1])*scale));
        drag=[e.clientX,e.clientY];
        redraw();
    };
    canvas.onlostpointercapture = () => { drag=null; };
    canvas.onwheel = e => {
        e.preventDefault();
        zoom=Math.max(.7,Math.min(2.5,zoom*Math.exp(-e.deltaY*.001)));
        redraw();
    };
    const resize = new ResizeObserver(redraw);
    resize.observe(canvas);
    draw();
    const cleanup = () => {
        if (canvas.orbitwatchCleanup !== cleanup) return;
        delete canvas.orbitwatchCleanup;
        resize.disconnect();
        cancelAnimationFrame(pending);
        image.onload=null;
        canvas.onpointerdown=canvas.onpointermove=canvas.onlostpointercapture=canvas.onwheel=null;
        pins.replaceChildren();
    };
    canvas.orbitwatchCleanup = cleanup;
    return cleanup;
}
