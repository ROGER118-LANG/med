document.getElementById('upload-form').onsubmit = function(event) {
    event.preventDefault(); // Evitar o envio padrão do formulário

    var formData = new FormData(this);

    fetch('/upload', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        document.getElementById('prediction').innerText = 'Previsão: ' + data.prediction;
        document.getElementById('confidence').innerText = 'Confiança: ' + data.confidence;
    })
    .catch(error => {
        console.error('Erro:', error);
    });
};
