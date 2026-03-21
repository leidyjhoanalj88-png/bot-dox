const express = require("express");
const app = express();

// Permitir JSON
app.use(express.json());

// Generador de código dinámico (6 dígitos)
function generateCode() {
  return Math.floor(100000 + Math.random() * 900000).toString();
}

// Endpoint principal
app.get("/api/dynamic", (req, res) => {
  res.json({
    code: generateCode(),
    expiresIn: 45
  });
});

// Endpoint de prueba
app.get("/", (req, res) => {
  res.send("Backend funcionando 🔥");
});

// Puerto (IMPORTANTE para hosting)
const PORT = process.env.PORT || 3000;

app.listen(PORT, "0.0.0.0", () => {
  console.log("Servidor corriendo en puerto " + PORT);
});