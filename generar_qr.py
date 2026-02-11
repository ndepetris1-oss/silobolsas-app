import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

# 🔧 Configuración
base_url = "https://silobolsas.onrender.com/form?id="
inicio = 1
fin = 100
salida = "qr_silobolsas.pdf"

# 📄 Configurar PDF
c = canvas.Canvas(salida, pagesize=A4)
ancho, alto = A4
x, y = 20*mm, alto - 40*mm
qrs_por_fila = 4
contador = 0

for i in range(inicio, fin + 1):
    qr_id = f"SB{i:04d}"
    url = f"{base_url}{qr_id}"

    # Generar imagen QR
    qr = qrcode.make(url)
    filename = f"temp_{qr_id}.png"
    qr.save(filename)

    # Dibujar en el PDF
    c.drawImage(filename, x, y, width=30*mm, height=30*mm)
    c.drawString(x, y - 5*mm, qr_id)
    c.drawString(x, y - 10*mm, url)

    # Avanzar posición
    contador += 1
    x += 45*mm

    if contador % qrs_por_fila == 0:
        x = 20*mm
        y -= 50*mm
        if y < 50*mm:
            c.showPage()
            y = alto - 40*mm

c.save()
print(f"✅ PDF generado: {salida}")
