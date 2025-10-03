async function getEstatisticas(endpoint) {
    try {
        const response = await fetch(`/api/estatisticas/${endpoint}`);
        if (!response.ok) {
            throw new Error(`Erro ao buscar dados: ${response.statusText}`);
        }
        const data = await response.json();
        return data;
    } catch (error) {
        console.error(error);
        alert('Erro ao carregar estatísticas.');
    }
}

async function carregarEstatisticas() {
    const endpoints = [
        { endpoint: 'inicio', id: 'totalVisitantesInicio' },
        { endpoint: 'genero', id: 'totalHomens' },
        { endpoint: 'genero', id: 'totalMulheres' },
        { endpoint: 'discipulado', id: 'discipuladosAtivos' },
        { endpoint: 'oracao', id: 'totalPedidosOracao' },
        { endpoint: 'origem', id: 'origemCadastro' },
        { endpoint: 'mensal', id: 'evolucaoMensal' },
        { endpoint: 'conversas', id: 'conversasEnviadasRecebidas' },
    ];

    for (let endpointInfo of endpoints) {
        const data = await getEstatisticas(endpointInfo.endpoint);
        document.getElementById(endpointInfo.id).innerHTML = `<strong>${data.valor}</strong>`;
    }
}

// Carregar as estatísticas assim que a página for carregada
window.onload = carregarEstatisticas;

document.getElementById('backToOptionsButton').addEventListener('click', () => {
    window.location.href = '/dashboard'; // Redireciona para a página principal
});
