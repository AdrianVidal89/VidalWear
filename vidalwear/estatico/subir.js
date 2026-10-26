// Subida de fotos: rápida y sin esperar.
//
// Cada foto se comprime EN EL MÓVIL antes de salir (1600 px, JPEG al 82 %):
// una foto de 4-12 MB se queda en 200-400 KB y sube en un segundo incluso por
// datos. Se suben en cola, de dos en dos, mientras la persona sigue haciendo
// fotos: nunca tiene que esperar a que termine una para hacer la siguiente.
(function () {
  'use strict';

  var LADO = 1600, CALIDAD = 0.82, A_LA_VEZ = 2;
  var raiz = document.getElementById('subida');
  if (!raiz) return;
  var categoria = raiz.dataset.categoria;
  var esOtros = raiz.dataset.otros === '1';
  var tanda = document.getElementById('tanda');
  var vacio = document.getElementById('vacio-tanda');
  var seguir = document.getElementById('seguir');
  var nombreOtros = document.getElementById('nombre-otros');

  var cola = [], activas = 0, pendientes = 0, subidas = 0, total = 0;

  function actualizarBoton() {
    if (!seguir) return;
    if (pendientes > 0) seguir.textContent = 'Subiendo… faltan ' + pendientes;
    else seguir.textContent = subidas > 0 ? seguir.dataset.con : seguir.dataset.sin;
  }

  // ------------------------------------------------------------ compresión
  // Se dibuja con un <img>: los navegadores actuales ya enderezan la foto
  // según su EXIF al pintarla, así que el canvas sale derecho.
  //
  // Las fotos se comprimen DE UNA EN UNA aunque se elijan 20 de golpe: una
  // foto de iPhone abierta ocupa ~50 MB de memoria y Safari recarga la página
  // si se abren muchas a la vez. La vista previa es una miniatura pequeña,
  // nunca la foto original.
  var MINI = 320;
  function cargar(fichero) {
    return new Promise(function (ok, mal) {
      var url = URL.createObjectURL(fichero);
      var img = new Image();
      img.onload = function () { URL.revokeObjectURL(url); ok(img); };
      img.onerror = function () { URL.revokeObjectURL(url); mal(new Error('no se puede leer')); };
      img.src = url;
    });
  }

  function aBlob(img, lado, calidad) {
    var w = img.naturalWidth, h = img.naturalHeight;
    var k = Math.min(1, lado / Math.max(w, h));
    var c = document.createElement('canvas');
    c.width = Math.round(w * k);
    c.height = Math.round(h * k);
    c.getContext('2d').drawImage(img, 0, 0, c.width, c.height);
    return new Promise(function (ok) {
      c.toBlob(function (blob) {
        c.width = c.height = 0;  // suelta la memoria del canvas ya (iOS es tacaño)
        ok(blob);
      }, 'image/jpeg', calidad);
    });
  }

  function comprimir(fichero) {
    return cargar(fichero).then(function (img) {
      return aBlob(img, LADO, CALIDAD).then(function (blob) {
        return aBlob(img, MINI, 0.7).then(function (mini) {
          img.src = '';
          if (!blob) throw new Error('sin memoria');
          return { blob: blob, vista: mini ? URL.createObjectURL(mini) : '' };
        });
      });
    });
  }

  var porComprimir = [], comprimiendo = false;
  function comprimirSiguiente() {
    if (comprimiendo || !porComprimir.length) return;
    comprimiendo = true;
    var t = porComprimir.shift();
    t.li.querySelector('.sello').textContent = '⋯';
    comprimir(t.fichero).then(function (r) {
      if (r.vista) t.li.querySelector('img').src = r.vista;
      return r.blob;
    }).catch(function () {
      // El navegador no sabe abrirla (p. ej. HEIC en un ordenador): se manda
      // tal cual y que la convierta el servidor.
      return t.fichero;
    }).then(function (blob) {
      cola.push({ li: t.li, blob: blob });
      siguiente();
      comprimiendo = false;
      // Un respiro entre foto y foto para que el móvil libere memoria.
      setTimeout(comprimirSiguiente, 30);
    });
  }

  // ----------------------------------------------------------------- fichas
  function nuevaFicha() {
    var li = document.createElement('li');
    li.className = 'ficha-subida subiendo';
    li.innerHTML =
      '<div class="marco"><img alt=""><span class="sello">⏳</span></div>' +
      '<div class="progreso"><i style="transform: scaleX(0)"></i></div>' +
      '<input type="text" maxlength="80" placeholder="' +
      (esOtros ? '¿Qué es?' : 'Nombre (opcional)') + '" aria-label="Nombre de la prenda">';
    tanda.prepend(li);
    vacio.hidden = true;
    var entrada = li.querySelector('input');
    if (esOtros && nombreOtros && nombreOtros.value.trim()) entrada.value = nombreOtros.value.trim();
    return li;
  }

  function estado(li, clase, sello) {
    li.classList.remove('subiendo', 'hecha', 'fallida');
    li.classList.add(clase);
    li.querySelector('.sello').textContent = sello;
  }

  function guardarNombre(li) {
    var entrada = li.querySelector('input');
    if (!li.dataset.id || entrada.dataset.guardado === entrada.value) return;
    entrada.dataset.guardado = entrada.value;
    fetch('/api/prendas/' + li.dataset.id + '/nombre', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nombre: entrada.value })
    });
  }

  // ------------------------------------------------------------------- cola
  function encolar(fichero) {
    var li = nuevaFicha();
    pendientes++;
    total++;
    actualizarBoton();
    li.querySelector('input').addEventListener('change', function () { guardarNombre(li); });
    porComprimir.push({ li: li, fichero: fichero });
    comprimirSiguiente();
  }

  function siguiente() {
    while (activas < A_LA_VEZ && cola.length) subir(cola.shift());
  }

  function subir(t) {
    activas++;
    var fd = new FormData();
    fd.append('categoria', categoria);
    fd.append('nombre', t.li.querySelector('input').value.trim());
    fd.append('foto', t.blob, 'foto.jpg');
    var x = new XMLHttpRequest();
    x.open('POST', '/api/prendas');
    var barra = t.li.querySelector('.progreso i');
    x.upload.onprogress = function (e) {
      if (e.lengthComputable) barra.style.transform = 'scaleX(' + (e.loaded / e.total).toFixed(3) + ')';
    };
    x.onload = function () {
      var r = {};
      try { r = JSON.parse(x.responseText); } catch (e) {}
      if (x.status === 200 && r.id) {
        t.li.dataset.id = r.id;
        t.li.querySelector('input').dataset.guardado = t.li.querySelector('input').value;
        guardarNombre(t.li);  // por si se escribió el nombre mientras subía
        estado(t.li, 'hecha', '✓');
        subidas++;
      } else {
        fallo(t, r.error || 'No se ha podido subir');
      }
      terminar();
    };
    x.onerror = function () { fallo(t, 'Sin conexión'); terminar(); };
    x.send(fd);
  }

  function fallo(t, texto) {
    estado(t.li, 'fallida', '!');
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'pequeno peligro';
    b.textContent = texto + ' · Reintentar';
    b.addEventListener('click', function () {
      b.remove();
      estado(t.li, 'subiendo', '…');
      pendientes++;
      actualizarBoton();
      cola.push(t);
      siguiente();
    });
    t.li.appendChild(b);
  }

  function terminar() {
    activas--;
    pendientes--;
    actualizarBoton();
    siguiente();
    if (pendientes === 0) total = 0;
    if (pendientes === 0 && esperando) { var d = esperando; esperando = null; location.href = d; }
  }

  function alElegir(e) {
    var ficheros = Array.prototype.slice.call(e.target.files);
    ficheros.forEach(encolar);
    e.target.value = '';  // que se pueda volver a elegir la misma foto
  }
  document.getElementById('camara').addEventListener('change', alElegir);
  document.getElementById('galeria').addEventListener('change', alElegir);

  // En «Otros», el nombre de arriba se copia a las fotos que aún no lo tengan.
  if (nombreOtros) {
    nombreOtros.addEventListener('change', function () {
      tanda.querySelectorAll('.ficha-subida').forEach(function (li) {
        var e = li.querySelector('input');
        if (!e.value.trim()) { e.value = nombreOtros.value.trim(); guardarNombre(li); }
      });
    });
  }

  // Si se pulsa «Siguiente» con fotos subiendo, se espera a que terminen.
  var esperando = null;
  document.querySelectorAll('[data-esperar]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      tanda.querySelectorAll('.ficha-subida').forEach(guardarNombre);
      if (pendientes > 0) {
        e.preventDefault();
        esperando = a.href;
        a.textContent = 'Terminando de subir…';
      }
    });
  });
  window.addEventListener('beforeunload', function (e) {
    if (pendientes > 0 && !esperando) { e.preventDefault(); e.returnValue = ''; }
  });
})();
