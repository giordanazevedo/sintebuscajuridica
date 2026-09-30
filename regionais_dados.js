const DADOS_REGIONAIS_INFO = [
    {
        nome: "ÁGUA BRANCA",
        presidente: "Maria do Socorro Nunes Motta",
        cidades: ["Água Branca", "Agricolândia", "Barro Durro", "Curralinhos", "Hugo Napoleão", "Lagoinha", "Olho D'Água", "Passagem Franca do Piauí", "São Pedro do Piauí", "Miguel Leão"],
        endereco: "Rua Vereador Abreu Pereira, 470, Centro, Água Branca-PI CEP: 64.460-000",
        fone: "(86) 3283-1917 / 9 9959-0411",
        email: "sinteab@bol.com.br"
    },
    {
        nome: "ALTOS",
        presidente: "Edivaldo de Sousa Martins",
        cidades: ["Altos", "Alto Longá", "Beneditinos", "Coivaras", "Novo Santo Antônio", "Pau D'arco"],
        endereco: "Conjunto Ludgero Raulino, Q 5, C 04, Altos-PI CEP: 64.290-000",
        fone: "(86) 3262-3055",
        email: "sintealtospi@gmail.com"
    },
    {
        nome: "AMARANTE",
        presidente: "André Vieira da Silva",
        cidades: ["Amarante", "Palmeirais"],
        endereco: "Rua José de Fontes, 647, Escalvado, Amarante-PI, CEP: 64.400-000",
        fone: "(86) 994225962",
        email: "avsilh@yahoo.com.br"
    },
    {
        nome: "BARRAS",
        presidente: "Roosevelt Veira de Carvalho",
        cidades: ["Barras", "Boa Hora", "Cabeceiras do Piauí", "Nossa Senhora dos Remédios", "Porto"],
        endereco: "Rua do Conjunto B, bairro Matadouro, Barras-PI CEP: 64.100-000",
        fone: "",
        email: ""
    },
    {
        nome: "BOM JESUS",
        presidente: "Ana Maria Soares de Sousa",
        cidades: ["Bom Jesus", "Alvorada do Gurguéia", "Cristino Castro", "Currais", "Palmeira do Piauí", "Redenção do Gurguêia", "Santa Luz"],
        endereco: "Av. Getúlio Vargas, 86, Bairro Miramar, Bom Jesus-PI CEP: 64.900-000",
        fone: "(89) 3562-2595",
        email: "sintebomjesus @hotmail.com"
    },
    {
        nome: "CAMPO MAIOR",
        presidente: "Marcilene Lima",
        cidades: ["Campo Maior", "Assunção do Piauí", "Buriti dos Montes", "Boqueirão", "Castelo do Piauí", "Cocal de Telha", "Jatobá", "Juazeiro do Piauí", "N. S. de Nazaré", "São Miguel do Tapuio", "São João da Serra", "Sigefredo Pacheco"],
        endereco: "Av. Santo Antonio, 940, Bairro-Lourdes, Campo Maior-PI CEP: 64.280-000",
        fone: "",
        email: ""
    },
    {
        nome: "CANTO DO BURITI",
        presidente: "Júnior Timóteo de Amorim",
        cidades: ["Canto do Buriti", "Colônia do Gurgueia", "Eliseu Martins", "Manoel Emidio", "Pajeu do Piauí", "Ribeira", "Tamboril"],
        endereco: "Rua Coelho Neto, 829, Centro, Canto do Buriti-PI CEP: 64.890-000",
        fone: "",
        email: "sintecdoburiti@hotmail.com"
    },
    {
        nome: "CORRENTE",
        presidente: "Sandra Marília Pereira",
        cidades: ["Corrente", "Avelino Lopes", "Barreiras do Piauí", "Cristalândia do Piauí", "Curimata", "Gilbués", "Julio Borges", "Monte Alegre do Piauí", "Morro Cabeça do Tempo", "Parnaguá", "Riacho Frio", "Santa Filomena", "São Gonçalo Gurgueia", "Sebastião Barros"],
        endereco: "Rua 8, B Nova Corrente, S/N, Corrente-PI CEP: 64.980-000",
        fone: "(89) 9 94718667",
        email: "sandramarilia2011@hotmail.com"
    },
    {
        nome: "DERMEVAL LOBÃO",
        presidente: "Josimar da Silva",
        cidades: ["Demerval Lobão", "Monsenhor Gil", "Lagoa do Piauí"],
        endereco: "Rua São Vicente, 531, Centro Demerval Lobão-PI, CEP: 64.390-000",
        fone: "",
        email: ""
    },
    {
        nome: "ESPERANTINA",
        presidente: "Francisca Correia da Rocha",
        cidades: ["Esperantina", "Batalha", "Campo Largo do Piauí", "Joaquim Pires", "Matias Olímpio", "Morro do Chapeú", "São João do Arraial"],
        endereco: "Rua Francisco Frederico Carvalho, 777, B- Rural, Esperantina-PI, CEP: 64.180-000",
        fone: "(86) 9 9986-5215 / 3383-1525",
        email: "regionalsindical@yahoo.com.br"
    },
    {
        nome: "FLORIANO",
        presidente: "Oberdan Siqueira Correia",
        cidades: ["Floriano", "Antônio Almeida", "Arraial", "Bertolinia", "Canavieira", "Flores do Piauí", "Francisco Aires", "Guadalupe", "Itaueira", "Jerumenha", "Landri Sales", "Marcos Parente", "Nazaré do Piauí", "Pavussu", "Porto Alegre", "Rio Grande do Piauí", "São Francisco do Piauí"],
        endereco: "Rua Antonio Neto, 1204, Floriano-PI, CEP: 64.800-000",
        fone: "(89) 3521-1355 / (86) 9 9917-0046",
        email: "sinteflo@hotmail.com"
    },
    {
        nome: "JAICÓS",
        presidente: "Maria Fatanilde Alves de Carvalho Silva",
        cidades: ["Jaicós", "Acauã", "Betania", "Caridade do Piauí", "Curral Novo", "Francisco Macedo", "Jacobina do Piauí", "Marcolândia", "Massapé", "Patos do Piauí", "Paulistana", "Padre Marcos", "Simões"],
        endereco: "Rua Juvenal Antão, 568, Serranópolis, Jaicós-PI, CEP: 64.575-000",
        fone: "(89) 3457-1173 / 9 9939-0067",
        email: "mariafatanilde@hotmail.com"
    },
    {
        nome: "JOSÉ DE FREITAS",
        presidente: "Maria Gorete de Carvalho Campos",
        cidades: ["José de Freitas", "Lagoa Alegre"],
        endereco: "Rua Edgar Gayoso, 515, Centro, José de Freitas,-PI, CEP: 64.110-000",
        fone: "(86) 9 9917-0090 / 3264-1054",
        email: "sintenrjf@gmail.com"
    },
    {
        nome: "LUZILÂNDIA",
        presidente: "Solange Maria Vasconcelos Barbosa",
        cidades: ["Luzilândia", "Joça Marques", "Morinhos", "Madeiros"],
        endereco: "Conj. José Martins Filho, Q-B, C- 03, Luzilândia-PI, CEP: 64.160-000",
        fone: "(96) 3393-1771 / (86) 9 9858-7567",
        email: "svbarbosa123@hotmail.com"
    },
    {
        nome: "OEIRAS",
        presidente: "Josevaldo de Jesus Lemos",
        cidades: ["Oeiras", "Campinas do Piauí", "Colônia do Piauí", "Cajazeiras", "Floresta do Piauí", "Santo Inácio do Piauí", "São José do Peixe", "Santa Rosa do Piauí", "São João da Varjota", "São Miguel do Fidalgo", "Tanque do Piauí"],
        endereco: "Rua Pe. Damasceno, 29, Centro, Oeiras-PI, CEP: 64.500-000",
        fone: "(89) 9 9939-0069",
        email: "sinteoeiraspi@gmail.com"
    },
    {
        nome: "PARNAÍBA",
        presidente: "Nadja Maria da Silva Araújo",
        cidades: ["Paranaíba", "Parnaíba", "Buriti dos Lopes", "Bom Princípio do Piauí", "Cajueiro da Praia", "Cocal", "Caruabas", "Cocal dos Alves", "Caxingó", "Ilha Grande do Piauí", "Luis Correia", "Murici dos Portelas"],
        endereco: "Rua Desembargador Freitas, 1247, Parnaíba-PI, CEP: 64.218-490",
        fone: "(86) 3322-1327 / (86) 9 9917-0019",
        email: "sinte-piphb@hotmail.com"
    },
    {
        nome: "PEDRO II",
        presidente: "Rafael Lopes Viana",
        cidades: ["Pedro II", "Domingos Mourão", "Lagoa do São Francisco"],
        endereco: "Rua Jacob Uchôa, 537, Centro, Pedro II-PI, CEP: 64.255-000",
        fone: "(86) 3271-2519 / (86) 9 9917-0184",
        email: "sintepedro2@hotmail.com"
    },
    {
        nome: "PICOS",
        presidente: "João Antônio de Sousa",
        cidades: ["Picos", "Alegrete do Piauí", "Bocaina", "Campo Grande do Piauí", "Dom Expedito Lopes", "Francisco Santos", "Germiniano", "Isaias Coelho", "Ipiranga do Piauí", "Itainopoles", "Monsenhor Hipólito", "Paquetá", "Pedro Laurentino", "Santo Antônio de Lisboa", "Santa Cruz do Piauí", "São João da Canabrava", "São José do Piauí", "Santana do Piauí", "Sussuapara", "Taquaralto", "Wall Ferraz", "Vila Nova", "Vera Mendes"],
        endereco: "Rua São Francisco, S/N, Centro, Picos-PI, CEP: 64.600-00",
        fone: "(89) 3422-3392",
        email: "sintepicos@gmail.com"
    },
    {
        nome: "PIO IX",
        presidente: "Antônia Josemaria Pinheiro",
        cidades: ["Pio IX", "Alagoinhas", "Caldeirão Grande do Piauí", "Fronteiras", "São Julião"],
        endereco: "Rua Deputado Sousa Santos, S/N, Centro, Pio IX-PI, CEP: 64.660-000",
        fone: "(89) 3454-1766",
        email: "sintepioix@hotmail.com"
    },
    {
        nome: "PIRACURUCA",
        presidente: "Maria do Rosário Pereira Gomes",
        cidades: ["Piracuruca", "São José do Divino", "São João da Fronteira"],
        endereco: "Rua Leonardo das Dores, S/N, Piracuruca-PI, CEP: 64.240-000",
        fone: "(86) 3343-1770 / (86) 9 9917-0196",
        email: "sinte-pi-piracuruca@r7.com"
    },
    {
        nome: "PIRIPIRI",
        presidente: "Rosa Maria da Silva",
        cidades: ["Piripiri", "Brasileira", "Capitão de Campos"],
        endereco: "Rua Martinho Sousa, 945, Piripiri-PI, CEP: 64.260-000",
        fone: "(86) 3276-1616 / (86) 9 9917-0047",
        email: "sinte-piripiri@hotmail.com"
    },
    {
        nome: "REGENERAÇÃO",
        presidente: "Maria das Mercês de Jesus Silva",
        cidades: ["Regeneração", "Angical do Piauí", "Jardim do Mulato", "São Gonçalo do Piauí"],
        endereco: "Rua Cônego Carino, S/N, Centro, Regeneração-PI, CEP: 64.490-000",
        fone: "(86) 9 9917-0047 / 3293-1322",
        email: "jesusmercesjesus@gmail.com"
    },
    {
        nome: "SÃO JOÃO DO PIAUÍ",
        presidente: "Dionísia Ribeiro da Silva",
        cidades: ["São João do Piauí", "Bela Vista", "Conceição do Canindé", "Campo Alegre do Fidalgo", "Capitão Gervasio Oliveira", "Lagoa do Barro", "Nova Santa Rita", "Paes Landim", "Simplicio Mendes", "Socorro do Piauí"],
        endereco: "Travessa Adail Coleho Maia, 419, São João do Piauí-PI, CEP: 64.670-000",
        fone: "(89) 3582-2468",
        email: ""
    },
    {
        nome: "SÃO RAIMUNDO NONATO",
        presidente: "Vanda Maria de Oliveira Costa Aragão",
        cidades: ["São Raimundo Nonato", "Anísio de Abreu", "Bonfim do Piauí", "Caracol", "Coronel José Dias", "Dirceu Arcoverde", "Dom Inocêncio", "Fartuna do Piauí", "Guaribas do Piauí", "Jurema do Piauí", "São Braz do Piauí", "São Lourenço do Piauí", "Várzea Branca"],
        endereco: "Rua Professor João, 120, Centro, São Raimundo Nonato-PI, CEP: 64.770-000",
        fone: "(89) 3582-2468 / (89) 9 9939-0072",
        email: "sintesrn@hotmail.com"
    },
    {
        nome: "UNIÃO",
        presidente: "Francisco Félix da Silva",
        cidades: ["União", "Miguel Alves"],
        endereco: "Rua da Pedreira, 941, Centro, União-PI, CEP: 64.120-000",
        fone: "(86) 3265-1192 / (86) 9 9917-0086",
        email: "sinteuniao2011@hotmail.com"
    },
    {
        nome: "URUÇUÍ",
        presidente: "Raimunda Martins Gomes",
        cidades: ["Uruçuí", "Baixa Grande do Ribeiro", "Ribeiro Gonçalves", "Sebastião Leal"],
        endereco: "Rua Projetada, S/N, Bela Vista, Uruçuí-PI, CEP: 64.860-000",
        fone: "(89) 3544-1293",
        email: "sinteurucui@hotmail.com"
    },
    {
        nome: "VALENÇA",
        presidente: "Alexsandro José Neris de Meneses",
        cidades: ["Valença", "Aroazes", "Elesbão Veloso", "Francinópolis", "Inhuma", "Lagoa do Sítio", "Novo Oriente do Piauí", "Pimenteiras", "Prata do Piauí", "São Felix do Piauí", "Santa Cruz dos Milagres", "Santo Antônio dos Milagres", "Várzea Grande"],
        endereco: "Rua Cel. Anibal Martins, 787, Centro, Valença-PI CEP: 64.300-000",
        fone: "(89) 3465-1151 / 9 9939-0031",
        email: "alexsandro.neris@hotmail.com"
    }
];

function procurarRegionalPorCidade(query) {
    const q = query.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
    for (const reg of DADOS_REGIONAIS_INFO) {
        // Verifica nome da regional
        const regNome = reg.nome.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
        if (regNome === q || regNome.includes(q)) return reg;
        
        // Verifica as cidades
        for (const cid of reg.cidades) {
            const cidNome = cid.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "").trim();
            if (cidNome === q || cidNome.includes(q)) return reg;
        }
    }
    return null;
}
