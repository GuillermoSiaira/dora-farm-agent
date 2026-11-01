# Base de Datos Técnica con Fuente para Modelo Matemático de Ganadería Bovina de Carne (Programación Lineal Quincenal) en Cinco Zonas

**Notas metodológicas y tipos de cambio utilizados (Reglas obligatorias):**
- **Argentina (Zonas 1, 2 y 3)**: Tipo de cambio oficial Banco de la Nación Argentina (BNA) / BCRA Vendedor al **31/10/2026** = **1.560,00 ARS/USD** (Comprador: 1.510,00 ARS/USD; Dólar MEP: 1.568,66 ARS/USD), según [TN Economía / BCRA - BNA (2026-10-31)](https://tn.com.ar/economia/2026/10/31/dolar-oficial-hoy-y-dolar-blue-a-cuanto-cotizan-este-sabado-31-de-octubre/). Cuando se citan coeficientes físicos o estructuras de costos de publicaciones anteriores (como el [Boletín N° 10 de SAGyP de 2014-05](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf), donde las tablas de los modelos están en texto extraíble a diferencia de los boletines de 2026 donde están como imagen), se indica explícitamente `dato más viejo` junto con su fecha.
- **Brasil (Zona 4 - Mato Grosso)**: Tipo de cambio oficial PTAX Venta del Banco Central do Brasil (BCB) al **29/10/2026** = **5,3744 BRL/USD** (Compra: 5,3738 BRL/USD), según [Banco Central do Brasil (2026-10-29)](https://www.bcb.gov.br/). Nota: En Brasil, 1 arroba (`@`) de peso vivo equivale a 30 kg de peso vivo (o 15 kg de carcasa con rendimiento del 50%).
- **Estados Unidos (Zona 5 - Iowa / Midwest)**: Moneda local = **USD** (1,00 USD/USD). Conversiones métricas: 1 libra (`lb`) = 0,45359237 kg; 1 quintal estadounidense (`cwt` = 100 lb) = 45,359237 kg; 1 tonelada corta (`short ton` = 2.000 lb) = 907,185 kg; 1 acre = 0,404686 ha; 1 bushel de maíz (`bu` = 56 lb) = 25,401 kg.

## A. Informe corto por zona (máximo 10 líneas por zona)

### 1. Cuenca del Salado (provincia de Buenos Aires, Argentina)
1. La Cuenca del Salado (incluyendo la Depresión de Laprida) abarca 36 partidos bonaerenses y es la principal región de cría vacuna de la Argentina, concentrando el 45,23% del stock provincial y el 47% de los vientres y terneros ([UNICEN / MAGyP-INTA-SENASA](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
2. Presenta suelos planos con drenaje impedido (capacidad de uso mayoritaria VIws), alcalinidad/salinidad e inundaciones periódicas alternadas con sequías primavero-estivales ([UNICEN / INTA](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
3. El sistema predominante es la cría vacuna sobre campo natural (95% en el modelo modal de 450 ha y 66% en el modelo mejorado con 26% de praderas y 8% de verdeos) ([SAGyP - Boletín N° 10](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf)).
4. El servicio se estaciona en primavera (octubre-diciembre o noviembre-enero, 90 días), con pariciones en invierno (julio-septiembre) y destete en otoño (marzo) con 6 a 8 meses de edad y 160-180 kg/cab ([INTA EEA Cuenca del Salado](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf); [SAGyP](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
5. Crecientemente los criadores anexan una recría corta de 4 meses (marzo a junio/julio) llevando machos de 175 a 250 kg y hembras de 170 a 240 kg sobre verdeos o excedentes de otoño para capturar mayor margen por hectárea ([SAGyP - Boletín N° 10](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
6. La receptividad del campo natural sostiene sin déficit invernal hasta 0,7 EV/ha (siendo crítica a 0,9-1,1 EV/ha en primaveras secas), pasando de 0,56 EV/ha en cría modal a 0,91 EV/ha en cría mejorada ([INTA EEA Cuenca del Salado](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf); [SAGyP](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
7. En septiembre de 2026 el ternero en la Cuenca del Salado cotizó a 6.572 ARS/kg vivo (4,21 USD/kg al TC BNA de 1.560 ARS/USD) y el margen bruto del modelo base alcanzó 317.750 ARS/ha (203,69 USD/ha) ([SAGyP - Tablero Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf); [SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
8. La estructura de costos en la cría modal es fuertemente fija (57% estructura e impuestos, 16% personal, 14% amortizaciones, 10% sanidad y 3% alimentación), frente a un 28% de gasto en alimentación en el modelo mejorado ([SAGyP - Boletín N° 10](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
9. Ante sequías o anegamientos, el productor ajusta carga mediante venta anticipada de vacas vacías/improductivas, destete anticipado o precoz y suplementación priorizando vacas de primera parición ([INTA EEA Cuenca del Salado](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf)).

### 2. Azul / centro de la provincia de Buenos Aires
1. El partido de Azul y el centro-sudoeste bonaerense (junto con Tandil, Olavarría, Bolívar, Daireaux y Coronel Suárez) conforman una zona de transición entre la Pampa Deprimida y los suelos agrícolas donde conviven la cría, la recría y el ciclo completo con terminación a pasto o corral ([UNICEN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download); [SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
2. El clima registra 945 mm de lluvia media anual, temperaturas medias de 7,8 °C (mínima) a 20,8 °C (máxima) y un período con heladas de 239 días entre marzo y noviembre ([UNICEN / SMN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
3. En planteos mixtos de Azul, el ciclo completo entora vaquillonas a los 15 meses (servicio de octubre a diciembre), desteta en marzo con 160-180 kg, recría sobre pasturas (festuca, tréboles, cebadilla, alfalfa) y verdeos de invierno (avena/raigrás) hasta noviembre, pastorea maíz de verdeo en diciembre-enero y termina a corral en febrero-marzo con 400 kg (machos) y 375 kg (hembras) ([UNICEN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
4. En el modelo oficial de Ciclo Completo Centro-Sudoeste de Buenos Aires (380 ha ganaderas dentro de 700 ha mixtas), se manejan 190 vacas (0,50 vacas/ha; 0,93 cab totales/ha; 117,2 kg carne/ha) sobre 66% campo natural, 26% praderas y 8% verdeos de invierno, vendiendo novillos de 390 kg y vaquillonas de 295 kg ([SAGyP - Boletín N° 10](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
5. La oferta forrajera presenta excedentes de febrero a julio y dos baches estacionales: fines de invierno (agosto-septiembre) por bajas temperaturas y falta de nitrógeno, y verano (noviembre-enero) cuando decaen las gramíneas templadas ([UNICEN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
6. Para cubrir esos baches, los productores difieren maíz en pie (marzo-julio) y pasturas de festuca (3.330 kg MS/ha acumulados entre marzo y junio) con rollos y silaje de maíz en autoconsumo durante la parición invernal, y siembran verdeos de verano (maíz o sorgo forrajero) ([UNICEN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
7. Los terneros y terneras "cola" de parición se encierran a corral de marzo a septiembre con grano de maíz/cebada o silaje de planta entera para igualar su desarrollo al resto del lote antes de salir a pasto ([UNICEN](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download)).
8. En 2026 los márgenes del ciclo completo retrocedieron un 13,4% trimestral por el encarecimiento relativo de los costos directos frente a la estabilidad del novillo gordo ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).

### 3. Zona núcleo (Pergamino, Argentina)
1. En la Zona Núcleo (Pergamino y norte de Buenos Aires / sur de Santa Fe) predomina la agricultura continua (soja, maíz y trigo-soja de 2°), por lo que la ganadería bovina se concentra en planteos intensivos de recría-invernada pastoril sobre suelos clase II-III o rotaciones agrícola-ganaderas y terminación en feedlot ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf); [UNNOBA / INTA Pergamino](https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y)).
2. SAGyP explicita en su anexo metodológico que no modela un establecimiento de cría en la Región Norte de Buenos Aires por ser la agricultura la actividad principal, evaluando en cambio los modelos de Invernada de Alta y Media Producción (Región Pampeana Subhúmeda / Santa Fe Centro), Feedlot (por administración y hotelería) y Recría a campo con terminación a corral ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
3. En el modelo de Invernada de Alta Producción (500 ha: 70% praderas base alfalfa y 30% verdeos de invierno, en rotación agrícola con maíz), ingresan terneros de 180 kg y salen novillos de 404 kg en 11,5 meses (ADPV 0,70 kg/día), sosteniendo una carga de 2,71 EV/ha (2,80 cab/ha) y produciendo 605 kg de carne/ha/año ([SAGyP - Boletín N° 10](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
4. En agosto de 2026, el margen bruto de la invernada de alta producción se ubicó en 432.552 ARS/ha (277,28 USD/ha al TC oficial BNA de 1.560 ARS/USD), superando al trigo en rotaciones con maíz aunque por debajo de la soja de 1° y el maíz ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
5. En el precio neto del novillo de invernada de alta producción en agosto de 2026, el 73% corresponde al costo de compra del ternero (relación compra/venta de 1,46), el 21% a los costos operativos y de estructura, y el 6% al resultado neto ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
6. En Pergamino, las pasturas perennes de festuca alta y leguminosas producen en promedio 5.400 kg MS/ha/año (rango de 3.500 a 7.200 kg MS/ha/año según lluvias, y hasta 12.000 kg MS/ha/año fertilizadas), con tasas de acumulación neta de 47,3 kg MS/ha/día en primavera normal y 15,6 kg MS/ha/día en otoño o años secos ([UNNOBA / INTA EEA Pergamino](https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y)).
7. El esquema combinado de recría a pasto lleva al ternero hasta 300 kg a campo y lo encierra 100 días a corral con ración exclusiva (maíz propio a 178 USD/t) para vender un novillito de 400 kg; en 2026 SAGyP demostró que alargar la recría a pasto (+30 kg con verdeo de verano) y acortar el encierre mejora un 27% el margen de recría y vuelve positivo el resultado conjunto ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).
8. En feedlot comercial (2,3 ciclos/año, con umbral mínimo de rentabilidad en 1,75 ciclos/año), la tarifa de hotelería de referencia es de 430 ARS/cab/día (0,28 USD/cab/día) ([SAGyP - Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)).

### 4. Mato Grosso (Brasil)
1. Mato Grosso posee el mayor rodeo bovino de Brasil y desarrolla su ganadería bajo clima tropical con estación lluviosa ("águas", octubre a abril) y estación seca marcada ("seca", mayo a septiembre), donde más del 95% del rebanho se cría en pasturas cultivadas de *Brachiaria* (*Urochloa*) y *Panicum* ([Embrapa Gado de Corte](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf)).
2. Coexisten sistemas extensivos sobre pasturas con algún grado de degradación (lotación 0,7 a 0,9 cab/ha, natalidad 60%, destete 54% con 160 kg) y sistemas intensificados o integrados con agricultura (ILP, soja-maíz safrinha/forraje) que alcanzan 3,0 cab/ha, natalidad del 82%, destete del 78% con 200 kg y faena a los 2,5 años ([Embrapa Gado de Corte - DOC 182](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf)).
3. En recría y engorde a pasto, el macho ingresa al destete (150-210 kg, 7@) pasando a boi magro (350-360 kg, 12@) y terminándose con 480-520 kg (16-18@), mientras que en semiconfinamiento (60 a 80 días sobre pasto diferido con concentrado al 0,7-2,0% del PV) o confinamento (70 a 120 días) se acelera el giro de capital ([Embrapa Gado de Corte](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf); [IMEA](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911)).
4. Según el 2° relevamiento 2026 del IMEA, Mato Grosso encierra 1,33 millones de cabezas en confinamento (48,31% con entrega a faena entre septiembre y noviembre, durante la entressafra), con un costo medio de la diária confinada de 13,62 BRL/cab/día en julio de 2026 (2,53 USD/cab/día al PTAX de 5,3744 BRL/USD) ([IMEA - Boletim N° 910](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/910)).
5. En el 2° trimestre de 2026, el Costo Operacional Total (COT) calculado por el IMEA en Mato Grosso se ubicó en 295,79 BRL/@ (55,04 USD/@) para Cría, 369,55 BRL/@ (68,76 USD/@) para Recría/Engorda y 182,25 BRL/@ (33,91 USD/@) para Ciclo Completo ([IMEA - Boletim N° 911](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911)).
6. En agosto de 2026 los precios en Mato Grosso alcanzaron 325,88 a 329,86 BRL/@ para boi gordo a plazo (60,64 a 61,38 USD/@), 306,11 a 308,82 BRL/@ para vaca gorda (56,96 a 57,46 USD/@), 3.322,83 BRL/cab (15,82 BRL/kg; 618,27 USD/cab) para bezerro de 7@ (210 kg) y 13,16 BRL/kg (2,45 USD/kg) para boi magro de 12@ ([IMEA - Boletim N° 911](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911)).
7. En octubre de 2026, el indicador CEPEA marcó récords nominales con el boi gordo en 389,9 BRL/@ (72,55 USD/@) y el bezerro (MS) en 3.573,0 BRL/cab (664,82 USD/cab) ([Farmnews / CEPEA](https://www.farmnews.com.br/mercado/preco-do-boi-gordo-e-bezerro-destaques-de-outubro-de-2026/)).
8. La comercialización tributa en Mato Grosso el FETHAB Gado (24,26% de la UPF/MT de 243,49 BRL = 59,07 BRL/cabeza o 10,99 USD/cab en 2026, con reducción para hembras según Ley 13.032/2025) y a nivel federal el FUNRURAL (1,5% sobre ingresos brutos para persona física o 2,05% para persona jurídica, con exención en compraventa de animales para cría/recría entre productores excepto 0,2% SENAR) ([Sygma / SEFAZ-MT](https://www.sygmasistemas.com.br/guia-calculo-fethab-mato-grosso/); [Sygma / RFB](https://www.sygmasistemas.com.br/funrural-calculo-e-aliquotas/)).

### 5. Iowa / Midwest (Estados Unidos)
1. En Iowa y el Corn Belt estadounidense, la ganadería de carne se articula estrechamente con la abundante oferta de maíz ($4,12 USD/bushel en 2026) y subproductos de la industria del etanol como los granos de destilería modificados (MDGS a $100/ton) y secos (DDGS a $200/ton) ([Iowa State University Extension - Ag Decision Maker File B1-21, Junio 2026](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
2. El sistema de cría (*Beef Cow-Calf*) utiliza pasturas permanentes en tierras no agrícolas (2,5 acres = 1,01 ha por vaca durante primavera-otoño), 4 acres (1,62 ha) de rastrojos de maíz (*corn stalks*) en otoño-invierno y 2,1 toneladas cortas (1.905 kg) de heno de alfalfa-brome durante el invierno, logrando un 92% de destete (*calf crop weaned*) ([ISU Extension - File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
3. La parición principal ocurre en primavera (marzo-abril) y el destete en otoño (octubre-noviembre) con 550 lb (249,5 kg) en machos y 500 lb (226,8 kg) en hembras ([ISU Extension - File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
4. La recría (*backgrounding*) dura 5 meses (150 días) y se realiza en invierno a corral con maíz y heno (llevando terneros de 450 lb / 204,1 kg a 750 lb / 340,2 kg, ADPV 0,91 kg/día) o en verano sobre pastura mejorada (0,7 acres = 0,28 ha/cab, llevando terneros de 525 lb / 238,1 kg a 750 lb / 340,2 kg, ADPV 0,68 kg/día) ([ISU Extension - File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
5. La terminación a corral (*feedlot finishing*) lleva novillos de año (*yearling steers*) de 750 lb (340,2 kg) a 1.350 lb (612,3 kg) en 6,5 meses (195 días; ADPV 1,40 kg/día), terneros (*steer calves*) de 550 lb (249,5 kg) a 1.350 lb (612,3 kg) en 9 meses (270 días; ADPV 1,35 kg/día), o vaquillonas (*yearling heifers*) de 700 lb (317,5 kg) a 1.350 lb (612,3 kg) en 270 días (ADPV 1,09 kg/día) ([ISU Extension - File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
6. En los presupuestos 2026 de ISU Extension, el costo total anual por unidad vaca en cría es de $1.147,98 USD ($698,98 variables y $449,00 fijos), mientras que el costo total de terminación a corral (incluyendo compra del animal) es de $3.468,14/cab en *yearling steers* (precio de equilibrio $2,57/lb = $5,67/kg) y $3.581,50/cab en *steer calves* (equilibrio $2,65/lb = $5,84/kg) ([ISU Extension - File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
7. Entre enero de 2024 y diciembre de 2025 (24 meses), los precios en Iowa subieron de $175,10 a $225,76/cwt (pico de $243,58/cwt = $5,37/kg en ago-2025) en novillos terminados *Choice*, y de $286,68 a $446,07/cwt (pico de $460,84/cwt = $10,16/kg en sep-2025) en terneros de 500-600 lb; para el presupuesto 2026 ISU proyecta $4,92/lb ($10,85/kg) para ternero y $3,74/lb ($8,25/kg) para novillito de 700-800 lb ([ISU Extension - File B2-12](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf); [File B1-21](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf)).
8. La venta de bovinos tributa la tasa federal *National Beef Checkoff* de $1,00 USD/cabeza por transacción (más $0,50 USD/cab de checkoff estatal en Iowa), sin retenciones a la exportación ([Cattlemen's Beef Board / USDA](https://www.beefboard.org/2024/07/09/new-independent-study-finds-each-national-beef-checkoff-dollar-returns-13-41/)).

## B. Tablas de datos por zona

### 1. Cuenca del Salado (provincia de Buenos Aires, Argentina)

| tema | dato | valor | unidad | fuente (con link) | fecha |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Actividades habituales | Cría modal y mejorada - Categoría que entra y que sale | Entra: Vaquillona de reposición propia (1° servicio a los 27 meses) y Toro de compra (650 kg) / Sale: Ternero destete, Ternera destete, Vaca gorda (447 kg), Vaca conserva (380 kg) y Toro rechazo (570 kg) | categoría | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Modelos Cría Cuenca del Salado)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo: coeficientes físicos de modelo SAGyP) |
| 1. Actividades habituales | Cría modal - Peso de salida ternero macho / ternera hembra al destete | 175 (macho) / 170 (hembra) | kg/cabeza | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 1. Actividades habituales | Cría mejorada - Peso de salida ternero macho / ternera hembra al destete | 180 (macho) / 160 (hembra) | kg/cabeza | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 10)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 1. Actividades habituales | Cría - Duración de lactancia hasta destete y meses típicos de servicio, parición y venta | Duración: 6 a 8 meses de lactancia / Servicio: octubre-diciembre (o noviembre-enero) / Parición: julio-septiembre / Venta terneros: marzo-abril | meses | [INTA EEA Cuenca del Salado - Estado de situación en la Cuenca del Salado (Pág. 2) y SAGyP Boletín N° 10 (Pág. 9)](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf) | 2019-10 (dato más viejo) |
| 1. Actividades habituales | Recría corta post-destete en campo de cría - Categoría, pesos, duración y mes de venta | Entra: Ternero (175 kg) y Ternera (170 kg) en marzo / Sale: Ternero recriado (250 kg) y Ternera recriada (240 kg) en junio-julio / Duración: 4 meses | kg/cabeza y meses | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 24)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 1. Actividades habituales | Engorde a pasto (invernada pura) y Engorde a corral puro en Cuenca del Salado | SIN FUENTE (SAGyP clasifica a la Cuenca del Salado con relación novillo/vaca de 0,07 y N+N/vaca de 0,13 como zona netamente de cría y no modela invernada pura ni feedlot puro dentro de esta subregión) | SIN FUENTE | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 82-83)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 |
| 2. Cría | % de preñez (rodeos monitoreados y módulo agroecológico INTA Cuenca del Salado) | >92 (módulo INTA Cuenca del Salado) / 92,5 (promedio 10 años establecimiento Cuenca del Salado) | % | [UNICEN / INTA - Planificación forrajera en la Cuenca del Salado (Pág. 20) y Valor Carne / INTA EEA Cuenca del Salado](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 2. Cría | % de destete (Cría Chica / Cría Modal / Cría Mejorada en Cuenca del Salado) | 70 (Chica) / 72 (Modal) / 80 (Mejorada) [rango regional INTA EEA Cuenca del Salado: 70 a 90] | % | [SAGyP - Boletín Trimestral N° 10 (Pág. 9-11) e INTA EEA Cuenca del Salado (Pág. 2)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 / 2019-10 (dato más viejo) |
| 2. Cría | % de mortandad y pérdidas reproductivas (preñez-parto y mortandad anual de vientres) | 6% pérdida preñez-parición y 3% mortandad anual de vacas adultas (2% mortandad + 3% refugo sanitario en vacas; 4% mortandad en terneras de reposición; 5% en vaquillonas 2° servicio) | % | [Sitio Argentino de Producción Animal / INTA Balcarce (Equivalencias Ganaderas, Pág. 2) y UNICEN (Pág. 52)](https://www.produccion-animal.com.ar/produccion_y_manejo_pasturas/pastoreo%20sistemas/70-equivalencias_ganaderas.pdf) | 2006 / 2020-11 (dato más viejo) |
| 2. Cría | % de reposición anual de vientres (Cría Chica / Cría Modal / Cría Mejorada) | 18 (Chica) / 22 (Modal) / 23 (Mejorada) | % | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 2. Cría | Edad al primer servicio de vaquillonas y edad de descarte | Edad al 1° servicio: 27 meses (SAGyP modal/mejorada) o 15 meses (sistema intensificado) / Edad exacta de descarte en años: SIN FUENTE (se reporta descarte por vejez del 6% anual del rodeo) | meses / % | [SAGyP - Boletín Trimestral N° 10 (Pág. 9-10) e INTA Equivalencias Ganaderas (Pág. 2)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 2. Cría | Toros cada 100 vacas (porcentaje de toros en modelos Cuenca del Salado) | 4 (Modal y Mejorada) / 5 (Chica) | toros/100 vacas (%) | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 3. Pasto y carga | Receptividad / Carga animal media anual en Cuenca del Salado | 0,37 (Cría Chica) / 0,56 (Cría Modal) / 0,70 (umbral seguro campo natural INTA) / 0,91 (Cría Mejorada) | EV/ha | [SAGyP - Boletín Trimestral N° 10 (Pág. 9-11) e INTA EEA Cuenca del Salado (Pág. 4)](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf) | 2019-10 (dato más viejo) |
| 3. Pasto y carga | Receptividad mensual/estacional del campo natural en Cuenca del Salado | Otoño: Mar 0,8, Abr 0,6, May 0,3 / Invierno: Jun 0,3, Jul 0,3, Ago 0,3 / Primavera: Sep 0,6, Oct 1,2, Nov 1,2 / Verano: Dic 1,0, Ene 0,6, Feb 0,8 | EV/ha/día | [UNICEN / Tablas Equivalencias CREA-INTA (Pág. 48)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 3. Pasto y carga | Producción anual de forraje de campo natural en Cuenca del Salado (Gral. Alvear) según fertilización fosforada | 3.891 (sin fertilizar, 0 kg P/ha: 613 kg MS pastos OIP anuales, 68 kg MS OIP perennes, 1.895 kg MS pastos PEO estivales, 25 kg MS leguminosas, 1.290 kg MS malezas) / 5.478 (con 29 kg P/ha) / 7.814 (con 66 kg P/ha) | kg MS/ha/año | [UNICEN / Rodríguez et al. (Pág. 35, Tabla 8)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 3. Pasto y carga | Producción de forraje de pastura de festuca templada diferida en otoño (marzo a junio) | 3.330 acumulados (Marzo: 36 kg MS/ha/día = 1.080 kg MS/ha; Abril: 38 kg MS/ha/día = 1.140 kg MS/ha; Mayo: 27 kg MS/ha/día = 810 kg MS/ha; Junio: 10 kg MS/ha/día = 300 kg MS/ha; con 65% eficiencia de cosecha = 2.164,5 kg MS/ha consumidos) | kg MS/ha | [UNICEN / Cangiano y Brizuela INTA (Pág. 50)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 3. Pasto y carga | Producción de forraje en kg MS/ha por estación de verdeos en Cuenca del Salado | SIN FUENTE en kg MS/ha por estación (las tablas zonales expresan la oferta mensual en raciones o EV/ha/día; ver Zona 2 para raciones mensuales de avena y sorgo) | SIN FUENTE | [UNICEN (Pág. 39-40, 48)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 |
| 3. Pasto y carga | Consumo diario de un Equivalente Vaca (EV) | 18,54 Mcal EM/día, equivalentes a: 11,384 kg MS/día (50% digestibilidad), 10,078 kg MS/día (60% digestibilidad), 8,003 kg MS/día (70% digestibilidad) o 10,0 kg MS/día como valor práctico de presupuestación | kg MS/EV/día (y Mcal EM/día) | [UBA FCV / INTA Balcarce - Texto de Estudio Carga Animal y Sistemas de Pastoreo (Pág. 5 y 14) y UNICEN (Pág. 50)](http://dpd.fvet.uba.ar/cartelera/00030355.pdf) | 2020 (dato más viejo) |
| 4. Suplementación y corral | Parámetros de conversión y costo de ración de corral en Cuenca del Salado | SIN FUENTE específica para Cuenca del Salado (los parámetros de engorde a corral y recría+corral de SAGyP se modelan para Zona Núcleo/Oeste; ver Zonas 2 y 3) | SIN FUENTE | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 58-66)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 |
| 5. Costos por cabeza y estructura | Sanidad obligatoria SENASA (vacunación antiaftosa y brucelosis) | Fiebre aftosa (2 campañas anuales en menores/según estrategia Resolución SENASA 711/2025 y Disp. 21/2026) y Brucelosis (terneras de 3 a 8 meses) / Costo monetario por dosis de vacuna en 2026: SIN FUENTE | calendario oficial | [SENASA - Disposición 21/2026 y Disposición 27/2026](https://www.argentina.gob.ar/normativa/nacional/norma-426404/texto) | 2026-06 / 2026-10 |
| 5. Costos por cabeza y estructura | Costos directos e indirectos históricos en Cría Modal Cuenca del Salado (450 ha, 260 vacas) | Personal: 120 ARS/cab (154 ARS/vientre, 89 ARS/ha) / Sanidad: 78 ARS/cab (100 ARS/vientre, 58 ARS/ha) / Alimentación: 24 ARS/cab (30 ARS/vientre, 18 ARS/ha) / Estructura e impuestos: 426 ARS/cab (549 ARS/vientre, 317 ARS/ha) / Amortizaciones: 101 ARS/cab (75 ARS/ha) / Total: 748 ARS/cab (557 ARS/ha) | ARS de 2014-05 (y proporción: 57% estructura, 16% personal, 14% amort., 10% sanidad, 3% alim.) | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 5. Costos por cabeza y estructura | Dotación de mano de obra y salario mensual de peón ganadero (2026) | 1 peón cada 600 vientres (mínimo 0,5 Equivalente Hombre por establecimiento) / Salario mensual: 789 USD/mes (1.230.840 ARS/mes al TC BNA de 1.560 ARS/USD del 31/10/2026) | USD/mes y ARS/mes | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76 y 86)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-08 / 2026-09 |
| 5. Costos por cabeza y estructura | Precio del gasoil para labores y fletes (2026) | 1,18 USD/litro (1.840,80 ARS/litro al TC BNA de 1.560 ARS/USD del 31/10/2026) | USD/litro y ARS/litro | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-08 / 2026-09 |
| 5. Costos por cabeza y estructura | Gastos de comercialización (comisión + flete + tasas) y desbaste en Cría Cuenca del Salado | Gastos de comercialización: 6,80% (Modal), 6,78% (Mejorada), 6,75% (Chica) sobre ventas brutas / Desbaste: 5% | % | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 5. Costos por cabeza y estructura | Margen bruto de Cría Cuenca del Salado (Modelo base actualizado a 2026) | 317.750 ARS/ha (203,69 USD/ha al TC oficial BNA venta de 1.560,00 ARS/USD del 31/10/2026) | ARS/ha y USD/ha | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 67)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 |
| 6. Precios por categoría | Ternero de invernada (Cuenca del Salado) - Agosto y Septiembre 2025 vs. Agosto y Septiembre 2026 | Ago-2025: 5.343 ARS/kg constante / Sep-2025: 5.640 ARS/kg constante / Ago-2026: 6.557 ARS/kg (4,20 USD/kg) / Sep-2026: 6.572 ARS/kg (4,21 USD/kg al TC BNA 1.560 ARS/USD) | ARS/kg vivo y USD/kg vivo | [SAGyP - Tablero de Precios Bovinos Agosto y Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf) | 2026-09 |
| 6. Precios por categoría | Liviano consumo (novillitos y vaquillonas hasta 390 kg) y Novillo pesado (+430 kg) - Septiembre 2026 | Liviano hasta 390 kg: 4.613 ARS/kg (2,96 USD/kg) en Sep-2026 y 4.834 ARS/kg (3,10 USD/kg) en Ago-2026 / Novillo +430 kg: 4.275 ARS/kg (2,74 USD/kg) en Sep-2026 y 4.414 ARS/kg (2,83 USD/kg) en Ago-2026 (TC BNA 1.560 ARS/USD) | ARS/kg vivo y USD/kg vivo | [SAGyP - Tablero de Precios Bovinos Agosto y Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf) | 2026-09 |
| 6. Precios por categoría | Índices Rosgan de Invernada y Cría - Septiembre 2026 | Terneros: 6.135,40 ARS/kg (3,93 USD/kg) / Terneras: 5.813,33 ARS/kg (3,73 USD/kg) / Terneros/as: 6.027,85 ARS/kg (3,86 USD/kg) / Novillos 1-2 años: 5.329,43 ARS/kg (3,42 USD/kg) / Novillos 2-3 años: 4.551,10 ARS/kg (2,92 USD/kg) / Vaquillonas invernada: 5.094,98 ARS/kg (3,27 USD/kg) / Vacas invernada: 3.221,24 ARS/kg (2,06 USD/kg) / PIRI general: 5.537,82 ARS/kg (3,55 USD/kg) (TC BNA 1.560 ARS/USD) | ARS/kg vivo y USD/kg vivo | [Rosgan - Índices de Precios Anuales Septiembre 2026](https://rosgan.com.ar/indices) | 2026-09 |
| 6. Precios por categoría | Relación vaquillona preñada / vaca conserva y relación ternero / novillo (2026) | 1 vaquillona preñada = 2,59 vacas conserva de ~400 kg (promedio histórico 10 años = 2,06) / Relación ternero/novillo = 1,46 (máximo anual en mayo 2026) / Relación ternero/novillito = 1,28 / Serie completa de los 24 meses mes a mes para las 6 categorías en Argentina: SIN FUENTE en tablas abiertas (los boletines publican gráficos de evolución y los tableros mensuales reportan el mes en curso y la comparación interanual de agosto y septiembre) | relación de precios | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 3, 71-72)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 |
| 7. Capital | Valor de un ternero de invernada (175 kg) y de una vaca de invernada/cría (400 kg) en 2026 | Ternero 175 kg (Cuenca del Salado a 6.572 ARS/kg): 1.150.100 ARS/cabeza (737,24 USD/cab) / Vaca de invernada 400 kg (Rosgan a 3.221,24 ARS/kg): 1.288.496 ARS/cabeza (825,96 USD/cab) / Vaquillona preñada (2,59 vacas de 400 kg): ~3.337.205 ARS/cabeza (2.139,23 USD/cab) al TC BNA 1.560 ARS/USD | ARS/cabeza y USD/cabeza | [SAGyP Tablero Septiembre 2026, Boletín N° 59 (Pág. 72) y Rosgan Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf) | 2026-09 |
| 7. Capital | Monto total de capital inmovilizado por hectárea actualizado a 2026 | SIN FUENTE del monto absoluto en ARS de 2026 (las hojas detalladas de los modelos en el Boletín N° 59 están insertadas como imágenes sin texto extraíble; en el Boletín N° 10 de 2014-05 la rentabilidad sobre capital sin tierra era 10,9% en cría modal y 12,8% en cría mejorada, con inmovilización permanente de 12 meses en cría y 4 meses en recría corta) | % y meses | [SAGyP - Boletín Trimestral N° 10 (Pág. 9-10, 24) y Boletín N° 59 (Pág. 8-10)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 / 2026-09 |
| 8. Impuestos, retenciones o tasas | Derechos de exportación (retenciones) e IVA sobre hacienda y carne bovina en Argentina | Derechos de exportación categoría vaca (cortes tipos A, B, C, D y E, excepto animales vivos): 0% (eliminados por Decreto 697/2024) / Resto de cortes bovinos: reducción del 25% sobre alícuota previa del 9% (= 6,75%) / IVA sobre venta de hacienda bovina en pie y carnes: 10,5% (Art. 28 Ley de IVA) / Valor monetario exacto de tasa de guía municipal y arancel DT-e SENASA en 2026: SIN FUENTE | % | [Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI - Tratamiento Impositivo de la Actividad Ganadera](https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer) | 2024-08 (vigente en 2026-09 según SAGyP Boletín N° 59 Pág. 46) |
| 9. Riesgos | Riesgos climáticos (sequía e inundación) y decisiones de manejo del productor en Cuenca del Salado | Riesgos: inundaciones periódicas por suelos planos de baja permeabilidad (VIws) y sequías de salida de invierno-primavera (mayo-septiembre) / Respuestas documentadas: 1) Clasificar potreros y rodeos por Estado Corporal (EC crítico = 3 en escala 1-5); 2) Venta de animales improductivos y vacas vacías; 3) Destete anticipado o precoz (o ecografía ovárica en diciembre para destetar solo vacas en anestro); 4) Adelantar servicio en lotes con EC >= 3 y suplementar priorizando vacas de 1° parición > multíparas > vaquillonas | estrategia técnica | [INTA EEA Cuenca del Salado - Estado de situación en la Cuenca del Salado (Pág. 2-7)](http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf) | 2019-10 (dato más viejo) |

### 2. Azul / centro de la provincia de Buenos Aires

| tema | dato | valor | unidad | fuente (con link) | fecha |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Actividades habituales | Ciclo completo con terminación a corral (Establecimiento en Azul, 1.451 ha) - Categorías, pesos, duración y meses | Cría: servicio oct-dic (entore 15 meses), destete en marzo con 160 kg (hembras) y 180 kg (machos) / Recría y engorde machos: 180 a 400 kg en 10-11 meses (ADPV 0,75 kg/día; pasturas/verdeos mar-nov, maíz verdeo dic-ene, corral terminación, venta dic 50%, ene 30%, feb 20%) / Recría y engorde hembras: 160 a 375 kg en 11 meses (ADPV 0,65 kg/día; venta fines ene-feb) / Engorde vacas vacías/viejas a corral: 2 meses (abril-mayo, ADPV 0,75 kg/día, +45 kg/cab, venta fines de mayo) | kg/cabeza, meses y kg/día | [UNICEN - Planificación forrajera para un establecimiento agrícola-ganadero en el partido de Azul (Pág. 26-27, 52-54)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 1. Actividades habituales | Ciclo Completo Centro-Sudoeste Buenos Aires (modelo oficial SAGyP, 380 ha ganaderas) - Categorías y pesos de venta | Destete a los 8 meses (ternero 180 kg, ternera 170 kg) / Venta de Vaquillonas recría/engorde: 295 kg / Venta de Novillos invernada: 390 kg / Venta de Vacas gordas: 447 kg / Venta de Vacas conserva: 380 kg / Venta de Toros rechazo: 570 kg (Compra toros: 650 kg) | kg/cabeza | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 31)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 2. Cría | % de preñez, % de destete, % de reposición y edad al 1° servicio (Establecimiento en Azul vs. Modelo SAGyP Centro-SO) | Azul (promedio 10 años): Preñez 92,5%, Destete 86%, Reposición anual de vientres 20%, Reposición anual de toros 20%, 1° servicio 15 meses / Modelo SAGyP Centro-SO: Destete 69%, Reposición 20%, 1° servicio 24 meses | % y meses | [UNICEN (Pág. 20, 52-53) y SAGyP Boletín N° 10 (Pág. 31)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 / 2014-05 (dato más viejo) |
| 2. Cría | % de mortandad y refugo por categoría en Azul | Vacas generales y vaquillonas 1° servicio: 2% mortandad + 3% refugo sanitario pre-servicio / Vaquillonas 2° servicio: 5% mortandad / Terneras de reposición: 4% mortandad (marzo-septiembre) | % | [UNICEN - Planificación forrajera en el partido de Azul (Pág. 52-53)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 2. Cría | Toros cada 100 vacas en Azul / Centro-Sudoeste | 4,0 (Modelo SAGyP Centro-SO) a 4,6 (Establecimiento Azul: 35 toros sobre 754 vacas generales, o 3,6 toros cada 100 vientres totales incluyendo vaquillonas) | toros/100 vacas (%) | [SAGyP Boletín N° 10 (Pág. 31) y UNICEN (Pág. 30)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 3. Pasto y carga | Receptividad y carga animal en Azul y Centro-Sudoeste | Establecimiento Azul (1.451 ha): 1.466,68 EV totales = 1,01 EV/ha (1,25 cab/ha) / Modelo SAGyP Centro-SO (380 ha): 0,50 vacas/ha, 0,93 cab/ha, 323 kg PV/ha, producción de carne 117,2 kg/ha/año | EV/ha y cab/ha | [UNICEN (Pág. 19, 30) y SAGyP Boletín N° 10 (Pág. 31)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 / 2014-05 (dato más viejo) |
| 3. Pasto y carga | Oferta forrajera mensual por recurso en zona Centro-Sudeste / Balcarce (en raciones/ha/mes = EV·día/ha/mes) | Campo natural (288 rac/ha/año): Ene 24, Feb 24, Mar 24, Abr 24, May 12, Jun 12, Jul 12, Ago 12, Sep 24, Oct 42, Nov 42, Dic 36 / Pastura base Alfalfa (672 rac/ha/año): Ene 66, Feb 48, Mar 54, Abr 42, May 24, Jun 24, Jul 24, Ago 30, Sep 30, Oct 105, Nov 108, Dic 117 / Pastura en implantación (195 rac/ha): Ago 30, Sep 45, Oct 45, Nov 45, Dic 30 / Verdeo Avena (489 rac/ha): Mar 30, Abr 60, May 45, Jun 60, Jul 60, Ago 60, Sep 72, Oct 72, Nov 30 / Verdeo Sorgo pastoreo (363 rac/ha): Dic 111, Ene 111, Feb 111, Mar 30 | raciones (EV·día)/ha/mes | [UBA FCV / INTA EEA Balcarce - Texto de Estudio Carga Animal y Sistemas de Pastoreo (Pág. 8, Tabla 1)](http://dpd.fvet.uba.ar/cartelera/00030355.pdf) | 2020 (dato más viejo) |
| 3. Pasto y carga | Equivalencias forrajeras de granos y silajes utilizados en Azul | Grano de maíz: 154 EV/tonelada / Grano de cebada: 152 EV/tonelada (rinde zonal estimado: 4.000 kg/ha) / Silo de planta entera de maíz (30% MS): 50 EV/tonelada de MS / Consumo por EV: 10 kg MS/día (18,54 Mcal EM/día) | EV/t y kg MS/EV/día | [UNICEN - Planificación forrajera en el partido de Azul (Pág. 48-50)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 3. Pasto y carga | Acumulación primaveral de pastizal natural con fertilización nitrogenada (INTA Balcarce / Pampa Deprimida) | Corte al 04/11: 2.433,2 kg MS/ha (0 kg N/ha) / 5.074,0 kg MS/ha (50 kg N/ha) / 5.700,2 kg MS/ha (100 kg N/ha) / 6.986,4 kg MS/ha (150 kg N/ha) / 6.995,9 kg MS/ha (200 kg N/ha) / 7.114,4 kg MS/ha (250 kg N/ha) | kg MS/ha | [UNICEN / Fernández Grecco y Agnusdei INTA Balcarce (Pág. 36, Tabla 9)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 4. Suplementación y corral | Aumento diario de peso (ADPV) por categoría en Azul y modelo Centro-Sudoeste | Terneros/novillitos en recría-invernada: 0,75 kg/día / Terneras de invernada: 0,65 kg/día / Terneras y vaquillonas de reposición: 0,50 kg/día / Toritos 1 año: 1,20 kg/día / Vacas vacías/viejas en corral de engorde (60 días): 0,75 kg/día / Conversión alimenticia y costo por kg de ración en Azul: SIN FUENTE (ver modelo de recría y corral de SAGyP en Zona 3) | kg/día | [UNICEN - Planificación forrajera en el partido de Azul (Pág. 52-54)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |
| 5. Costos por cabeza y estructura | Costos directos e indirectos en Ciclo Completo Centro-Sudoeste Buenos Aires (380 ha, 190 vacas) | Personal: 338 ARS/cab (626 ARS/vientre, 313 ARS/ha; 24% del costo total) / Sanidad: 97 ARS/cab (179 ARS/vientre, 90 ARS/ha; 7%) / Alimentación: 337 ARS/cab (623 ARS/vientre, 312 ARS/ha; 24%) / Estructura e impuestos: 519 ARS/cab (959 ARS/vientre, 480 ARS/ha; 37%) / Amortizaciones: 118 ARS/cab (218 ARS/vientre, 109 ARS/ha; 8%) / Costo Total: 1.408 ARS/cab (1.303 ARS/ha) / Gastos comercialización: 7,5% / Desbaste: 4% | ARS de 2014-05 y % | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 31)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 5. Costos por cabeza y estructura | Precio de maíz e insumos operativos nacionales en 2026 | Maíz: 178 USD/t (277.680 ARS/t) / Salario peón: 789 USD/mes (1.230.840 ARS/mes) / Gasoil: 1,18 USD/litro (1.840,80 ARS/litro) al TC oficial BNA de 1.560 ARS/USD del 31/10/2026 | USD y ARS | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-08 / 2026-09 |
| 6. Precios por categoría | Precios de referencia de hacienda aplicables a Buenos Aires (Septiembre 2026) | Ternero invernada: 6.572 ARS/kg (4,21 USD/kg) / Liviano consumo hasta 390 kg: 4.613 ARS/kg (2,96 USD/kg) / Novillo pesado +430 kg: 4.275 ARS/kg (2,74 USD/kg) / Vaca invernada (Rosgan): 3.221,24 ARS/kg (2,06 USD/kg) al TC BNA 1.560 ARS/USD / Serie mensual completa de 24 meses por categoría: SIN FUENTE en publicaciones abiertas | ARS/kg vivo y USD/kg vivo | [SAGyP Tablero Septiembre 2026 y Rosgan Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf) | 2026-09 |
| 7. Capital | Capital y tiempos de inmovilización en Ciclo Completo Centro-Sudoeste / Azul | Vientres: 12 meses / Recría-engorde de machos propios: 10 a 11 meses (de marzo a dic/ene/feb) / Recría-engorde de hembras propias: 11 meses (marzo a ene/feb) / Engorde de vacas de refugo a corral: 2 meses (abril-mayo) / Rentabilidad histórica sobre capital sin tierra en modelo Centro-SO: 3,2% | meses y % | [UNICEN (Pág. 52-54) y SAGyP Boletín N° 10 (Pág. 31)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 / 2014-05 (dato más viejo) |
| 8. Impuestos, retenciones o tasas | Régimen impositivo nacional sobre hacienda y carne (Argentina) | Derechos de exportación carne de vaca (A-E): 0% (Decreto 697/2024) / Derechos de exportación resto carne bovina: 6,75% (reducción del 25% sobre 9%) / IVA hacienda bovina en pie: 10,5% / Tasas municipales de guía en Azul 2026: SIN FUENTE | % | [Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI](https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer) | 2024-08 / 2026-09 |
| 9. Riesgos | Riesgos climáticos y forrajeros en Azul y manejo del productor | Déficits estacionales de forraje en invierno (agosto-septiembre, por heladas durante 239 días/año) y verano (noviembre-enero), además de anegamientos en suelos bajos / Respuestas: encierre a corral de terneros/as cola de parición (marzo-septiembre) con grano o silaje de maíz; diferimiento de maíz en pie y pasturas de festuca con rollos y silaje en autoconsumo para vacas en parición; rejuvenecimiento de agropiro y campo natural con fósforo/nitrógeno e implantación de raigrás anual y verdeos de verano (maíz/sorgo) | estrategia técnica | [UNICEN - Planificación forrajera en el partido de Azul (Pág. 21, 26-28, 32-40)](https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download) | 2020-11 (dato más viejo) |

### 3. Zona núcleo (Pergamino, Argentina)

| tema | dato | valor | unidad | fuente (con link) | fecha |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Actividades habituales | Invernada de Alta Producción (con suplementación, 500 ha) - Categorías, pesos y duración | Entra: Ternero de 180 kg / Sale: Novillo de 404 kg / Duración: 11,5 meses (ADPV: 0,70 kg/día) / Meses de compra/venta: compra en otoño (zafra mar-may), venta a fines de verano/otoño siguiente | kg/cabeza y meses | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 34) y Boletín N° 59 (Pág. 43, 47)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 / 2026-09 |
| 1. Actividades habituales | Invernada de Media Producción (sin suplementación, 500 ha) e Invernada Santa Fe Centro (700 ha) | Media Producción: Entra ternero 180 kg, Sale novillo 399 kg en 15,8 meses (ADPV 0,50 kg/día) / Santa Fe Centro: Entra ternero 180 kg, Sale novillo 427,5 kg en 22,2 meses (ADPV 0,40 kg/día) | kg/cabeza y meses | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 33, 35)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 1. Actividades habituales | Recría a campo + Terminación a corral (consumo interno) y Engorde de novillo pesado a corral (exportación) | Recría + Corral liviano: Entra ternero 180 kg a pasto hasta 300 kg, entra a corral con 300 kg durante 100 días (3,3 meses) en dos tandas sucesivas y sale novillito de 400 kg (variante recría larga: entra a corral con 330 kg) / Corral novillo pesado: Entra novillito recriado de 250 kg y sale novillo pesado de 480 kg (+44 días adicionales de encierre respecto al liviano) / Feedlot puro: 2,3 ciclos anuales (~5,2 meses por ciclo) | kg/cabeza y días/ciclos | [SAGyP - Boletín Trimestral N° 59 (Pág. 58-66) y Boletín N° 10 (Pág. 58)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 / 2014-05 |
| 2. Cría | Parámetros de cría en Zona Núcleo (Pergamino) | SIN FUENTE de modelo oficial para Zona Núcleo (SAGyP explicita en Pág. 82 del Boletín N° 59 que no modela cría en la Región Norte de Buenos Aires porque la actividad principal es la agricultura; el stock de Pergamino registra 51.613 vacas, 18.781 terneros y 20.020 terneras = relación ternero+ternera/vaca de 75,2% y 2.114 toros = 4,1 toros/100 vacas) | % y cabezas | [SAGyP Boletín N° 59 (Pág. 82) y UNICEN Anexo MAGyP Stock Pergamino (Pág. 46)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 / 2018-12 |
| 3. Pasto y carga | Receptividad / Carga animal media anual en Invernada (Alta Producción, Media Producción y Santa Fe Centro) | Alta Producción (70% praderas, 30% verdeos invierno): 2,71 EV/ha (2,80 cab/ha; 847 kg PV/ha; 605 kg carne/ha/año) / Media Producción (80% praderas, 20% verdeos invierno): 1,44 EV/ha (1,64 cab/ha; 492 kg PV/ha; 260 kg carne/ha/año) / Santa Fe Centro (80% praderas, 20% campo natural): 0,51 EV/ha (0,60 cab/ha; 75 kg carne/ha/año) | EV/ha y cab/ha | [SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 33-35)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf) | 2014-05 (dato más viejo) |
| 3. Pasto y carga | Producción de forraje de pasturas de festuca alta + leguminosas en INTA EEA Pergamino | Promedio anual en Pergamino: 5.400 kg MS/ha/año (rango según precipitaciones: 3.500 a 7.200 kg MS/ha/año; hasta 12.000 kg MS/ha/año con fertilización) / Tasa de acumulación neta diaria en Pergamino: 47,3 kg MS/ha/día en primavera húmeda (15/08 al 15/12/2020) y 15,6 kg MS/ha/día en otoño (15/03 al 15/06) y primavera seca / Eficiencia de pastoreo a ras del suelo: 35,9% (otoño) a 62,8% (primavera), y 50% en mezclas base alfalfa | kg MS/ha/año y kg MS/ha/día | [UNNOBA / INTA EEA Pergamino - Eficiencia de pastoreo y acumulación neta de forraje en Festuca arundinacea en Pergamino (Pág. 1, 10, 16-19)](https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y) | 2020 / 2021 (dato más viejo) |
| 3. Pasto y carga | Consumo diario de un Equivalente Vaca (EV) | 18,54 Mcal EM/día = 8,003 a 11,384 kg MS/día según digestibilidad (70% a 50%) | kg MS/EV/día | [UBA FCV / INTA Balcarce (Pág. 5 y 14)](http://dpd.fvet.uba.ar/cartelera/00030355.pdf) | 2020 (dato más viejo) |
| 4. Suplementación y corral | Engorde a corral y Recría+Corral - Días de encierre, ganancia diaria, servicio de hotelería y precio de maíz (2026) | Días de encierre en terminación de recría: 100 días (de 300 a 400 kg => ADPV = 1,00 kg/día) / Ciclos anuales de feedlot puro: 2,3 ciclos/año (umbral de indiferencia: 1,75 ciclos/año) / Tarifa servicio de hotelería de feedlot (febrero 2026): 430 ARS/cab/día (0,28 USD/cab/día al TC BNA 1.560 ARS/USD) / Precio grano de maíz (agosto 2026): 178 USD/t = 0,178 USD/kg (277,68 ARS/kg) / Relación maíz/novillo (agosto 2026): 56 kg de novillo por tonelada de maíz (promedio histórico: 102 kg/t) / Conversión alimenticia exacta del cuadro de feedlot (en imagen en PDF 2026): SIN FUENTE | días, kg/día, ARS/cab/día, USD/kg | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 58-66, 74, 76)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 |
| 5. Costos por cabeza y estructura | Composición del precio neto del novillo e incidencia de costos en Invernada de Alta Producción (agosto 2026) | Compra de ternero (CT): 73% (vs. 69% en ago-2025) / Costos directos, estructura y amortizaciones (C): 21% (vs. 25% en ago-2025) / Resultado Neto (RN): 6% (vs. 6% en ago-2025) / En Invernada Santa Fe: 67% compra ternero, 25% costos, 8% resultado neto | % del precio neto del novillo | [SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 43)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-08 / 2026-09 |
| 5. Costos por cabeza y estructura | Margen bruto de Invernada de Alta Producción (actualizado a 2026) y estructura porcentual de costos | Margen Bruto (2026): 432.552 ARS/ha (277,28 USD/ha al TC BNA 1.560 ARS/USD) / Estructura porcentual del costo total (sin compra de ternero, Boletín N° 10 Pág. 34): Alimentación 68%, Estructura e impuestos 17%, Personal 10%, Sanidad 3%, Amortizaciones 2% / Gastos comercialización: 6,5% en compra de ternero y 7,0% en venta de novillo / Mortandad en invernada: 2% / Desbaste: 5% | ARS/ha, USD/ha y % | [SAGyP - Boletín Trimestral N° 59 (Pág. 67) y Boletín N° 10 (Pág. 34)](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) | 2026-09 / 2014-05 |
| 6. Precios por categoría | Precios Rosgan (Bolsa de Comercio de Rosario, referencia Zona Núcleo) y MAG Cañuelas - Septiembre 2026 | Rosgan (Sep-2026): Terneros 6.135,40 ARS/kg (3,93 USD/kg), Terneras 5.813,33 ARS/kg (3,73 USD/kg), Novillos 1-2 años 5.329,43 ARS/kg (3,42 USD/kg), Novillos 2-3 años 4.551,10 ARS/kg (2,92 USD/kg), Terneros Holando 4.956,45 ARS/kg (3,18 USD/kg), Vaquillonas invernada 5.094,98 ARS/kg (3,27 USD/kg), Vacas invernada 3.221,24 ARS/kg (2,06 USD/kg) / SAGyP/MAG (Sep-2026): Liviano consumo hasta 390 kg 4.613 ARS/kg (2,96 USD/kg), Novillo +430 kg 4.275 ARS/kg (2,74 USD/kg) (TC BNA 1.560 ARS/USD) / Ventaja promedio novillo pesado vs. novillito liviano en 2026: +0,72% con picos mensuales >12% | ARS/kg vivo y USD/kg vivo | [Rosgan Septiembre 2026, SAGyP Tablero Septiembre 2026 y Boletín N° 59 (Pág. 69)](https://rosgan.com.ar/indices) | 2026-09 |
| 7. Capital | Valor de reposición del ternero de invernada (180 kg) y tiempos de inmovilización del capital | Ternero de 180 kg (a 6.135,40 ARS/kg Rosgan Sep-2026): 1.104.372 ARS/cabeza (707,93 USD/cab al TC BNA 1.560 ARS/USD) / Inmovilización: 11,5 meses en Invernada de Alta Producción, 15,8 meses en Invernada de Media Producción, 22,2 meses en Invernada Santa Fe Centro, y 100 días (3,3 meses) en la etapa de terminación a corral | ARS/cab, USD/cab y meses | [Rosgan Septiembre 2026 y SAGyP Boletín N° 10 (Pág. 33-35) y Boletín N° 59 (Pág. 62)](https://rosgan.com.ar/indices) | 2026-09 |
| 8. Impuestos, retenciones o tasas | Impuestos y retenciones sobre la hacienda y la carne (Argentina) | Derechos de exportación categoría vaca (cortes A-E): 0% (Decreto 697/2024) / Derechos de exportación resto cortes bovinos: 6,75% / IVA hacienda y carne bovina: 10,5% | % | [Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI](https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer) | 2024-08 / 2026-09 |
| 9. Riesgos | Riesgos climáticos y de mercado en Zona Núcleo / Pampeana y respuesta del productor | Riesgos: sequía primavero-estival (como la primavera seca y cálida de 2021 en Pergamino que redujo la densidad de macollos de festuca de 1.948 a 559 macollos/m2 con pastoreo severo a 5 cm) y desfasaje de la relación compra/venta (1,46 en 2026) / Respuestas: mantener remanente post-pastoreo de 8 a 11 cm (900-1.150 kg MS verde/ha) para evitar pérdida de macollos por estrés térmico en diciembre-enero; alargar la recría a pasto (+30 kg con verdeo de verano) y acortar los días de encierre a corral para reducir el consumo de maíz y mejorar un 27% el margen de recría | estrategia técnica | [UNNOBA / INTA Pergamino (Pág. 14, 19-20) y SAGyP Boletín N° 59 (Pág. 65-66)](https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y) | 2021 / 2026-09 |

### 4. Mato Grosso (Brasil)

| tema | dato | valor | unidad | fuente (con link) | fecha |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Actividades habituales | Cría, Recría y Engorda a pasto en Mato Grosso / Brasil Central - Categorías y pesos de entrada y salida | Cría: Entra novilha (1° cría a los 2,5 años en ILP o 4 años en pasto degradado), Sale bezerro/a al destete (7 meses) con 160 a 210 kg (7@ = 210 kg en indicador IMEA) / Recría a pasto: Macho entra con 150-210 kg y sale boi magro con 350-360 kg (12@); Hembra entra con 140-180 kg y sale con 270-305 kg / Engorda a pasto: Macho entra con 350-360 kg y sale boi gordo con 480 kg (edad de faena: 2,5 años en ILP a 4 años en sistema extensivo); Hembra entra con 270 kg y sale con 400 kg | kg/cabeza y meses/años | [Embrapa Gado de Corte - DOC 182 (Pág. 7, 16, 26, 28, 30) e IMEA Boletim N° 911 (Pág. 2-3)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 (dato más viejo) / 2026-08 |
| 1. Actividades habituales | Semiconfinamento y Confinamento (corral) - Categorías, pesos, duración y meses de entrega | Semiconfinamento (en época seca): Macho entra con 400 kg y sale con 460 kg en 60 días (ADPV 1,0 kg/día; o 80 días entrando con 360 kg en pasto diferido de 8 t MS/ha); Novilha/vaca entra con 320 kg y gana 50-70 kg / Confinamento: 1) Novilhos castrados (18-30 meses): entran con 350-420 kg, salen con 480-520 kg en 70 a 100 días; 2) Machos inteiros/tourinhos (18-30 meses): entran con 370-440 kg, salen con 500-550 kg en 90 a 120 días; 3) Novilhas (20-30 meses): entran con 280-320 kg, salen con 360-420 kg en 60 a 90 días; 4) Vacas de descarte (>3 años): entran con 340-420 kg, salen con 400-460 kg en 50 a 70 días / Ventana de venta del confinamento en MT: 48,31% se entrega entre septiembre y noviembre (entressafra) | kg/cabeza y días | [Embrapa Gado de Corte - Nutrição de Bovinos de Corte Cap. 9 (Pág. 127, 132) e IMEA Boletim N° 910 (Pág. 2)](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf) | 2015 (dato más viejo) / 2026-08 |
| 2. Cría | % de natalidad, % de destete y % de mortalidad (Pastura degradada vs. Pastura recuperada con ILP) | Pastura degradada: Natalidad 60%, Mortalidad hasta destete 8%, Destete 54%, Mortalidad post-destete 4% / Pastura recuperada con ILP: Natalidad 82%, Mortalidad hasta destete 3%, Destete 78%, Mortalidad post-destete 1% | % | [Embrapa Gado de Corte - DOC 182 Diagnóstico para o planejamento da propriedade (Pág. 7, Tabela 1)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 (dato más viejo) |
| 2. Cría | % de reposición anual de vientres, edad de descarte y relación toro:vaca en Mato Grosso | SIN FUENTE de valor único fijo en las tablas abiertas de IMEA/Embrapa (el protocolo de diagnóstico DOC 182 releva la relación touro:vaca y el % de descarte anual en cada propiedad; la tasa de desfrute total del rodeo pasa de 17% en pasto degradado a 30-35% en ILP) | % | [Embrapa Gado de Corte - DOC 182 (Pág. 7, 10, 24)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 (dato más viejo) |
| 3. Pasto y carga | Receptividad / Lotación por nivel tecnológico y en período seco (UA/ha y animales/ha, donde 1 UA = 450 kg PV) | Pasto degradado: 0,7 a 0,9 anim/ha (30 a 45 kg carne/ha/año) / Pasto mejorado: 1,5 anim/ha (60 kg/ha/año) / Pasto intensivo: 2,0 anim/ha (90 kg/ha/año) / Intensivo + suplemento: 2,2 anim/ha (120 kg/ha/año) / + Confinamento: 2,5 anim/ha (150 kg/ha/año) / + Integración ILP: 3,0 anim/ha (230 a 330 kg/ha/año) / Recría-engorda intensiva: 5,0 anim/ha (450 kg/ha/año) / En período seco (mayo-septiembre) con suplementación estratégica: 1,0 UA/ha (y 1,0 a 2,0 UA/ha en semiconfinamento) | animales/ha y UA/ha | [Embrapa Gado de Corte - DOC 182 (Pág. 7, 10, Tabelas 1 y 3) y Cap. 9 (Pág. 123, 126)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 / 2015 (dato más viejo) |
| 3. Pasto y carga | Masa de forraje acumulada (vedação / diferimiento) para la estación seca en Brasil Central | 4.000 a 6.000 kg MS/ha al inicio de la seca (diferimiento de 1/3 del área en febrero para uso en junio-julio y 2/3 en marzo para uso en agosto-septiembre) / Hasta 8.000 kg MS/ha con diferimiento prolongado y fertilización nitrogenada / Producción en kg MS/ha desagregada por las 4 estaciones para campo natural y pasturas en MT: SIN FUENTE | kg MS/ha | [Embrapa Gado de Corte - Nutrição de Bovinos de Corte Cap. 9 (Pág. 122, 126-127)](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf) | 2015 (dato más viejo) |
| 3. Pasto y carga | Equivalencias en Unidad Animal (UA = 450 kg PV) y consumo diario | Vaca preñada/lactante: 1,20 UA / Vaca vacía: 1,00 UA / Novilla 2-3 años (305 kg): 0,75 UA / Novilla 1-2 años (230 kg): 0,60 UA / Bezerro/a (150 kg): 0,44 UA / Macho 1-2 años (255 kg): 0,65 UA / Macho 2-3 años (360 kg): 0,85 UA / Macho 3-4 años (450 kg): 1,00 UA / Toro (>600 kg): 1,50 UA / Oferta en confinamiento: 10 kg/cab/día en adaptación hasta 18 kg/cab/día en dieta final (75% concentrado : 25% voluminoso en base seca) | UA/cabeza y kg/día | [Embrapa Gado de Corte - DOC 182 (Pág. 15-16, Tabela 8) y Cap. 9 (Pág. 134, Quadros 9.5 y 9.6)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 / 2015 (dato más viejo) |
| 4. Suplementación y corral | Ganancia diaria de peso (GMD) según cultivar forrajero y nivel de suplementación | En pasturas perennes (g/día): B. humidicola 400, B. decumbens 480, B. brizantha cv. Xaraés 480, cv. Marandu 500, cv. Piatã 530, Andropogon 550, Panicum cv. Massai 600, cv. Tanzânia 650, cv. Mombaça 650, Tifton 750 / Anuales: Sorgo forrajero 900, Milheto 950, Avena/Azevém 1.000 / En época seca: Sal mineral con 30% urea (consumo ~100 g/UA/día) = mantenimiento de peso; Sal proteinado (consumo 1 a 3 g/kg PV/día) = 0,20 a 0,40 kg/día; Semiconfinamento (concentrado al 0,7% a 2,0% del PV durante 60-80 días) = ~1,00 kg/día / En confinamento (70-120 días): ~1,30 a 1,50 kg/día / Conversión alimenticia exacta de confinamento en MT en 2026: SIN FUENTE | g/día y kg/día | [Embrapa Gado de Corte - DOC 182 (Pág. 9, Tabela 2) y Cap. 9 (Pág. 123-127, 132)](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf) | 2011-06 / 2015 (dato más viejo) |
| 4. Suplementación y corral | Costo de la diária confinada en Mato Grosso (Julio 2026) | 13,62 BRL/cabeza/día (+3,57% interanual vs. 2025), equivalente a 2,53 USD/cabeza/día al PTAX venta del BCB de 5,3744 BRL/USD del 29/10/2026 (con oferta final de 18 kg de ración/día equivale a ~0,76 BRL/kg o 0,14 USD/kg) | BRL/cab/día y USD/cab/día | [IMEA - Boletim Semanal Bovinocultura de Corte N° 910 (Pág. 2) y BCB PTAX](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/910) | 2026-07 / 2026-08 |
| 5. Costos por cabeza y estructura | Costo Operacional Total (COT) por actividad en Mato Grosso (serie trimestral 2025-2026 de IMEA) | Cría: 281,82 (2T/25), 279,64 (3T/25), 287,62 (4T/25), 290,71 (1T/26), 295,79 BRL/@ en 2T/26 (= 55,04 USD/@) / Recría/Engorda: 324,89 (2T/25), 325,71 (3T/25), 334,94 (4T/25), 351,63 (1T/26), 369,55 BRL/@ en 2T/26 (= 68,76 USD/@) / Ciclo Completo: 169,10 (2T/25), 172,94 (3T/25), 177,76 (4T/25), 178,01 (1T/26), 182,25 BRL/@ en 2T/26 (= 33,91 USD/@) [TC BCB PTAX 29/10/2026 = 5,3744 BRL/USD] / Desagregado en R$/cab de sanidad, mano de obra y estructura en 2026: SIN FUENTE en el boletín semanal abierto | BRL/@ y USD/@ | [IMEA - Boletim Semanal Bovinocultura de Corte N° 911 (Pág. 3) y BCB PTAX](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911) | 2026-06 / 2026-08 |
| 5. Costos por cabeza y estructura | Calendario sanitario de referencia (Embrapa Gado de Corte) | Fiebre aftosa (según estatus sanitario estadal/MAPA), Brucelosis en bezerras, Clostridiosis en bezerros a los 4 y 7 meses de edad, vacuna contra diarrea neonatal en hembras gestantes (4 meses antes del parto), botulismo (anual), rabia (zonas endémicas), vermifugación (novilhas del destete a los 2 años y vacas en periparto) y control de ectoparásitos (mosca de los cuernos, garrapata y berne) | calendario técnico | [Embrapa Gado de Corte - DOC 182 (Pág. 25, 29, 31)](https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf) | 2011-06 (dato más viejo) |
| 6. Precios por categoría | Precios en Mato Grosso por categoría (IMEA Agosto 2026 y comparativo Ago-2025 / Jul-2026) | Boi gordo a prazo (MT, 17-21/08/2026): 325,88 a 329,86 BRL/@ (60,64 a 61,38 USD/@) [media 3 semanas ago/26: 328,33 BRL/@ = 61,09 USD/@] / Vaca gorda a prazo (MT, 17-21/08/2026): 306,11 a 308,59 BRL/@ (56,96 a 57,42 USD/@) / Bezerro 7@ (210 kg, MT): 3.093,06 BRL/cab (20-24/07/26) a 3.322,83 BRL/cab (17-21/08/26; 15,82 BRL/kg = 618,27 USD/cab o 2,94 USD/kg) / Boi magro 12@ (360 kg, MT): 13,16 BRL/kg = 4.737,60 BRL/cab (2,45 USD/kg = 881,51 USD/cab) / Bezerra de ano 6@ (180 kg, MT): 10,14 BRL/kg (ago/25), 12,45 BRL/kg (jul/26), 12,80 BRL/kg (ago/26 = 2,38 USD/kg) / Novilha 8,5@ (255 kg, MT): 9,68 BRL/kg (ago/25), 11,21 BRL/kg (jul/26), 11,71 BRL/kg (ago/26 = 2,18 USD/kg) / Vaca solteira (MT): 9,23 BRL/kg (ago/25), 10,50 BRL/kg (jul/26), 10,94 a 11,06 BRL/kg (ago/26 = 2,04 a 2,06 USD/kg) [TC BCB PTAX 29/10/2026 = 5,3744 BRL/USD] | BRL/@, BRL/kg, BRL/cab y USD | [IMEA - Boletim Semanal Bovinocultura de Corte N° 911 (Pág. 2-3) y N° 910 (Pág. 2-3)](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911) | 2026-08 |
| 6. Precios por categoría | Evolución de precios CEPEA (2025 vs. Septiembre y Octubre 2026) y estacionalidad | Boi gordo CEPEA: 319,2 BRL/@ (fin de 2025) -> 364,3 BRL/@ (sep-2026) -> 389,9 BRL/@ al 30/10/2026 (+22,1% en 2026; 72,55 USD/@) / Bezerro CEPEA (MS): 3.066,6 BRL/cab (fin de 2025; 434,4 BRL/@) -> 3.446,1 BRL/cab (sep-2026; 517,7 BRL/@) -> 3.573,0 BRL/cab al 30/10/2026 (+16,5% en 2026; 534,7 BRL/@; 664,82 USD/cab al PTAX de 5,3744 BRL/USD) / Estacionalidad: mayores precios en la entressafra (periodo seco, especialmente septiembre-noviembre, con futuros B3 nov/26 en 406,90 BRL/@) / Serie completa de los 24 meses mes a mes para todas las categorías en MT: SIN FUENTE en boletines abiertos | BRL/@, BRL/cab y USD | [Farmnews / CEPEA - Preço do boi gordo e bezerro: destaques de outubro de 2026](https://www.farmnews.com.br/mercado/preco-do-boi-gordo-e-bezerro-destaques-de-outubro-de-2026/) | 2026-10 |
| 7. Capital | Valor de un ternero (bezerro 210 kg), boi magro (360 kg) y vaca solteira, y relación de troca en MT (Agosto 2026) | Bezerro 210 kg (7@): 3.322,83 BRL/cab (618,27 USD/cab) / Boi magro 360 kg (12@ a 13,16 BRL/kg): 4.737,60 BRL/cab (881,51 USD/cab) / Vaca solteira (ej. 390 kg a 11,06 BRL/kg): 4.313,40 BRL/cab (802,58 USD/cab) / Relación de troca boi gordo (21@) / bezerro (210 kg): 2,07 a 2,15 bezerros por boi gordo en jul-ago 2026 (vs. 2,29 en ago-2025) / Tiempo de inmovilización: 70 a 120 días en confinamento, 60 a 80 días en semiconfinamento, 12 a 24 meses en recría-engorda a pasto | BRL/cab, USD/cab y cab/cab | [IMEA - Boletim N° 911 (Pág. 2-3) y N° 910 (Pág. 2)](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911) | 2026-08 |
| 8. Impuestos, retenciones o tasas | FETHAB Gado y FETHAB Carne en Mato Grosso (vigencia prorrogada hasta diciembre 2026 por Lei Estadual N° 13.357 del 13/05/2026) | UPF/MT base (Enero 2025 mantenida para 2026 por Lei 13.002/2025 y Lei 13.357/2026): 243,49 BRL (45,31 USD) / FETHAB Gado en pie para faena o salida interestatal/exportación: 11,5% UPF/MT (FETHAB básico) + 11,5% UPF/MT (FETHAB adicional hasta 31/12/2026) + 1,26% UPF/MT (entidad de la cadena INPECMT/IMAmt) = 24,26% de la UPF/MT por cabeza = 59,07 BRL/cabeza (10,99 USD/cab al PTAX de 5,3744 BRL/USD), con reducción porcentual para hembras enviadas a faena según Lei 13.032/2025 y Decreto 1.940/2026 / FETHAB Carne en exportación: 0,03% de la UPF/MT por kg (= 0,073 BRL/kg) | % de UPF/MT, BRL/cab y USD/cab | [Sygma Sistemas / SEFAZ-MT - Guia Cálculo FETHAB MT 2026 y SEFAZ-MT Decreto 1.940/2026](https://www.sygmasistemas.com.br/guia-calculo-fethab-mato-grosso/) | 2026-01 / 2026-05 |
| 8. Impuestos, retenciones o tasas | FUNRURAL y SENAR sobre comercialización de bovinos en Brasil (Lei 13.606/2018) | Produtor Rural Pessoa Física (modalidad comercialización): 1,5% sobre el valor bruto de venta (1,2% INSS + 0,1% RAT + 0,2% SENAR) / Produtor Rural Pessoa Jurídica (modalidad comercialización): 2,05% (1,7% INSS + 0,1% RAT + 0,25% SENAR) / Exención: venta de ganado destinado a reproducción o cría/recría directamente entre productores rurais está exenta de INSS/RAT, pagando únicamente 0,2% (PF) o 0,25% (PJ) de SENAR | % sobre facturación bruta | [Sygma Sistemas / Receita Federal - Funrural cálculo e alíquotas (Lei 13.606/2018)](https://www.sygmasistemas.com.br/funrural-calculo-e-aliquotas/) | 2025-01 / 2026 |
| 9. Riesgos | Riesgo de estación seca (mayo a septiembre) y degradación de pasturas, y estrategias del productor en MT | Riesgos: caída abrupta de crecimiento y lignificación de pasturas tropicales entre mayo y septiembre (seca) y degradación de pasturas (que reduce la productividad de 300 a 30 kg carne/ha/año) / Respuestas técnicas: 1) Vedação/diferimiento escalonado de pasturas (1/3 en febrero y 2/3 en marzo para acumular 4 a 6 t MS/ha) con lotación de ~1 UA/ha; 2) Suplementación en seca con sal mineral con 30% urea (100 g/UA/día para mantenimiento) o sal proteinado (1-3 g/kg PV/día para ganar 200-400 g/día); 3) Semiconfinamento por 60-80 días o confinamento (aliviando pasturas en la seca y vendiendo el 48,31% entre septiembre y noviembre); 4) Renovación de pasturas mediante Integración Lavoura-Pecuária (ILP) | estrategia técnica | [Embrapa Gado de Corte - Cap. 9 (Pág. 121-129), DOC 182 (Pág. 6-10) e IMEA Boletim N° 910 (Pág. 2)](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf) | 2015 / 2026-08 |

### 5. Iowa / Midwest (Estados Unidos)

| tema | dato | valor | unidad | fuente (con link) | fecha |
| :--- | :--- | :--- | :--- | :--- | :--- |
| 1. Actividades habituales | Cría (Beef Cow-Calf, Calves Sold) - Categorías, pesos de salida y calendario | Entra: Vaquillona de reposición (0,20 cab/unidad vaca) y Toro ($5.000/cab, 0,04 toros/vaca) / Sale: Ternero macho destetado de 550 lb (249,5 kg; 0,46 cab vendidas/vaca), Ternera destetada de 500 lb (226,8 kg; 0,26 cab vendidas/vaca) y Vaca de descarte (cull cow) de 1.350 lb (612,3 kg; 0,18 cab vendidas/vaca) / Duración ciclo anual: 12 meses (parición primavera mar-abr, destete y venta otoño oct-nov) | lb/cabeza, kg/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21: 2026 Livestock Enterprise Budgets for Iowa (Pág. 15-16)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 1. Actividades habituales | Recría de invierno a corral (Backgrounding Steer Calves, Winter Corn & Hay Ration) - Pesos y duración | Entra: Ternero (steer calf) de 450 lb (204,1 kg) en otoño (oct-nov) / Sale: Novillito feeder de 750 lb (340,2 kg) en primavera (mar-abr) / Duración: 5 meses (150 días; ganancia total 300 lb = 136,1 kg) | lb/cabeza, kg/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 14)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 1. Actividades habituales | Recría de verano a pasto (Backgrounding Steer Calves, Summer Improved Pasture) - Pesos y duración | Entra: Ternero (steer calf) de 525 lb (238,1 kg) en primavera (mayo) / Sale: Novillito feeder de 750 lb (340,2 kg) en otoño (septiembre-octubre) / Duración: 5 meses (150 días; ganancia total 225 lb = 102,1 kg) | lb/cabeza, kg/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 14)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 1. Actividades habituales | Engorde a corral de novillitos de año (Finishing Yearling Steers) - Pesos y duración | Entra: Yearling feeder steer de 750 lb (340,2 kg) / Sale: Fed steer terminado de 1.350 lb (612,3 kg) / Duración: 6,5 meses (195 días; ganancia total 600 lb = 272,2 kg) | lb/cabeza, kg/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 11)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 1. Actividades habituales | Engorde a corral de terneros (Finishing Steer Calves) y de vaquillonas de año (Finishing Yearling Heifers) - Pesos y duración | Steer Calves: Entra ternero de 550 lb (249,5 kg), Sale novillo terminado de 1.350 lb (612,3 kg), Duración 9 meses (270 días; ganancia 800 lb = 362,9 kg) / Yearling Heifers: Entra vaquillona de 700 lb (317,5 kg), Sale vaquillona terminada de 1.350 lb (612,3 kg), Duración 270 días / 9 meses (ganancia 650 lb = 294,8 kg) | lb/cabeza, kg/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 12-13)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 2. Cría | % de preñez, % de destete, % de mortandad, % de reposición, descarte y toros cada 100 vacas en Iowa | % de preñez: SIN FUENTE en B1-21 (se reporta directamente destete) / % de destete (calf crop weaned): 92% de las vacas del rodeo (0,90 terneros comercializados/retenidos por vaca tras mortandad) / % de reposición anual de vientres: 20% (0,20 bred heifer por vaca) / % de mortandad anual de vacas y vaquillonas de reposición: 2% / Tasa de venta anual de vacas de descarte (cull cows): 18% (0,18 cab/vaca/año; vida útil productiva implícita ~5 pariciones, vida útil de toros = 3 años) / Toros cada 100 vacas: 4,0 (1 toro cada 25 vacas = 0,04 bull/cow unit) | % y toros/100 vacas | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 15-16)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 3. Pasto y carga | Receptividad (AUM/acre y EV/ha) y producción anual de forraje por tipo de pastura y rastrojo en Iowa | Bluegrass sin mejorar: 1,0-1,5 ton/acre (2.242-3.363 kg/ha) y 3,0 AUM/acre (7,41 AUM/ha) / Bluegrass mejorado con leguminosa o N: 1,5-2,5 ton/acre (3.363-5.604 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) / Lotus (birdsfoot trefoil) + gramínea: 3,0-4,0 ton/acre (6.725-8.967 kg/ha) y 5,0 AUM/acre (12,36 AUM/ha) / Pasto ovillo o bromegrass puro: 3,0-4,0 ton/acre (6.725-8.967 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) / Pasto ovillo o bromegrass + leguminosa o N: 4,0-5,0 ton/acre (8.967-11.209 kg/ha) y 6,5 AUM/acre (16,06 AUM/ha) / Gramíneas estivales (warm season): 4,0-5,0 ton/acre (8.967-11.209 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) / Alfalfa + gramínea: 4,0-6,0 ton/acre (8.967-13.450 kg/ha) y 6,0 AUM/acre (14,83 AUM/ha) / Rastrojo de maíz (cornstalks): 0,5-1,0 ton/acre (1.121-2.242 kg/ha; 3.467 lb MO/acre en ASL-1636) y 0,7 AUM/acre (1,73 AUM/ha) / El pastoreo rotativo incrementa la producción ~25% / Desagregado trimestral por estación en kg MS/ha: SIN FUENTE en C2-23 (en invierno no hay crecimiento por nieve/congelamiento) | short tons/acre, kg/ha y AUM/acre (y AUM/ha) | [Iowa State University Extension - Ag Decision Maker File C2-23: Computing a Pasture Rental Rate (Pág. 2, Table 1, Ago 2025) y ASL-1636](https://www.extension.iastate.edu/agdm/wholefarm/pdf/c2-23.pdf) | 2025-08 |
| 3. Pasto y carga | Superficie asignada por cabeza en los presupuestos 2026 de Iowa y consumo diario por Animal Unit (AU) | Cría (Beef Cow-Calf): 2,5 acres (1,01 ha) de pastura permanente ($63/acre) + 4,0 acres (1,62 ha) de rastrojo de maíz ($13/acre) + 2,1 short tons (1.905 kg) de heno alfalfa-brome + 4 bushels (101,6 kg) de maíz por unidad vaca/año / Recría de verano (Summer Backgrounding): 0,7 acres (0,28 ha) de pastura mejorada ($102/acre) por novillito durante 5 meses / Consumo de 1 Animal Unit (AU, vaca de 1.000 lb con ternero): 26 lb/día de forraje seco a estufa (11,79 kg MS/día, 100% MS) o 30 lb/día de forraje secado al aire (13,61 kg/día al 87% MS) / Equivalencias AU (Table 2 C2-23): Vaca adulta 1,0-1,4 AU; Toro 1,5 AU; Novillito/vaquillona de año 0,7-0,9 AU; Vaquillona 2 años 1,0-1,2 AU; Ternero 0,4 AU | acres/cab, ha/cab y kg MS/AU/día | [ISU Extension File B1-21 (Pág. 14-15), File C2-23 (Pág. 2) y NDSU / NRCS Range and Pasture Handbook](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 / 2025-08 |
| 4. Suplementación y corral | Finishing Yearling Steers (750 a 1.350 lb en 195 días) - ADPV, dieta, conversión y costo de ración (2026) | Ganancia total: 600 lb (272,2 kg) en 195 días => ADPV = 3,08 lb/día (1,40 kg/día) / Dieta Maíz + Heno: 60 bu maíz (3.360 lb = 1.524,1 kg a $4,12/bu = $247,20) + 1,14 tons MDGS (2.280 lb = 1.034,2 kg a $100/ton = $114,00) + 0,30 tons heno (600 lb = 272,2 kg a $81/ton = $24,30) + 95 lb suplemento/mineral (43,1 kg a $0,23/lb = $21,85) -> Total alimento tal cual: 6.335 lb (2.873,5 kg), Conversión tal cual: 10,56 kg alimento/kg ganancia (conversión en base seca ~7,9 kg MS/kg ganancia considerándose ~50% MS en MDGS), Costo total alimentación: $407,35 USD/cab ($0,1418 USD/kg tal cual; $0,679 USD/lb de ganancia = $1,50 USD/kg ganado) / Dieta Maíz + Silaje: 49,25 bu maíz ($202,91) + 1,14 tons MDGS ($114,00) + 1,32 tons silaje de maíz ($65,21 a $49,40/ton) + 95 lb suplemento ($21,85) -> Costo total alimentación: $403,97 USD/cab | kg/día, kg/kg y USD | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 2, 3, 11)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 4. Suplementación y corral | Finishing Steer Calves (550 a 1.350 lb en 270 días) - ADPV, dieta, conversión y costo de ración (2026) | Ganancia total: 800 lb (362,9 kg) en 270 días => ADPV = 2,96 lb/día (1,34 kg/día) / Dieta Maíz + Heno: 69 bu maíz (3.864 lb = 1.752,7 kg; $284,28) + 1,40 tons MDGS (2.800 lb = 1.270,1 kg; $140,00) + 0,53 tons heno (1.060 lb = 480,8 kg; $42,93) + 135 lb suplemento (61,2 kg; $31,05) -> Total alimento tal cual: 7.859 lb (3.564,8 kg), Conversión tal cual: 9,82 kg/kg (en base seca ~7,5 kg MS/kg), Costo alimentación: $498,26 USD/cab ($0,1398 USD/kg tal cual; $1,37 USD/kg ganado) / Dieta Maíz + Silaje: 50 bu maíz ($206,00) + 1,40 tons MDGS ($140,00) + 2,26 tons silaje de maíz ($111,64) + 135 lb suplemento ($31,05) -> Costo alimentación: $488,69 USD/cab | kg/día, kg/kg y USD | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 12)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 4. Suplementación y corral | Finishing Yearling Heifers (700 a 1.350 lb en 270 días) y Backgrounding Steer Calves (150 días) - ADPV y costos de alimentación (2026) | Yearling Heifers (ganan 650 lb = 294,8 kg en 270 días => ADPV = 2,41 lb/día = 1,09 kg/día): Dieta Maíz+Heno (80 bu maíz $329,60 + 1,5 tons MDGS $150,00 + 0,40 tons heno $32,40 + 160 lb supl. $36,80) = $548,80 USD/cab (8.440 lb tal cual = 3.828,3 kg; conversión tal cual 12,98 kg/kg; Dieta Maíz+Silaje = $552,58 USD/cab) / Winter Backgrounding (450 a 750 lb en 150 días => ADPV = 2,00 lb/día = 0,91 kg/día): 27 bu maíz ($111,24) + 0,5 tons heno alfalfa-brome ($40,50) + 80 lb supl. ($18,40) = $170,14 USD/cab (2.592 lb tal cual = 1.175,7 kg; conversión tal cual 8,64 kg/kg; $0,1447 USD/kg ración) / Summer Backgrounding a pasto (525 a 750 lb en 150 días => ADPV = 1,50 lb/día = 0,68 kg/día): 0,7 acres pastura ($71,40) + fertilización ($14,00) + 35 lb supl. ($8,05) = $93,45 USD/cab / Referencia Iowa Beef Center (novillos Holstein hasta 1.000 lb): ADPV ~3,0 lb/día (1,36 kg/día), consumo 18-20 lb MS/día (8,2-9,1 kg MS/día), conversión 6,0 a 7,0 kg MS/kg ganancia | kg/día, kg/kg y USD/cab | [ISU Extension File B1-21 (Pág. 13-14) e Iowa Beef Center (Feeding Holstein Steers, Pág. 1)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 5. Costos por cabeza y estructura | Costos detallados por cabeza en Cría (Beef Cow-Calf, 1 unidad vaca) en Iowa (2026) | Alimentación total: $451,48 USD/vaca (Pastura 2,5 ac $157,50 + Fertilización pastura $50,00 + Rastrojos 4 ac $52,00 + Heno 2,1 t $170,10 + Maíz 4 bu $16,48 + Sal y minerales 60 lb $5,40) / Veterinaria y sanidad: $25,00 USD/vaca / Maquinaria, combustible y reparaciones: $24,00 USD/vaca / Comercialización y varios: $20,00 USD/vaca / Interés sobre capital operativo (7,11% anual por 6 meses): $18,50 USD/vaca / Mano de obra (8 horas a $20,00/h): $160,00 USD/vaca / Total Costos Variables: $698,98 USD/vaca / Costos Fijos: Maquinaria, equipos y alambrados $105,00 USD/vaca ($41,62 USD/ha sobre 2,5 acres) + Interés/seguro sobre rodeo al 10% $296,00 USD/vaca + Depreciación/reposición de toro $48,00 USD/vaca = Total Costos Fijos $449,00 USD/vaca / COSTO TOTAL ANUAL: $1.147,98 USD/unidad vaca | USD/vaca/año (moneda local = USD) | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 15-16)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 5. Costos por cabeza y estructura | Costos detallados por cabeza en Recría (Backgrounding) y Feedlot (Finishing) en Iowa (2026) | 1) Finishing Yearling Steers (Maíz+Heno): Compra novillito (750 lb a $3,74/lb) $2.805,00 + Interés hacienda (6,5 m al 7,11%) $108,03 + Alimentación $407,35 + Sanidad $8,00 + Maquinaria $11,20 + Comercialización/transporte $16,00 + Interés var. $8,52 + Mano de obra (2,5 h a $20/h) $50,00 + Mortandad (1% compra + 0,5% var.) $31,64 + Costos Fijos instalaciones $22,40 = Costo Total $3.468,14 USD/cab / 2) Finishing Steer Calves (Maíz+Heno): Compra ternero (550 lb a $4,92/lb) $2.706,00 + Interés hacienda (9 m) $144,30 + Alimentación $498,26 + Sanidad $10,00 + Maquinaria $17,60 + Comercialización $14,00 + Interés var. $14,39 + Mano de obra (4 h) $80,00 + Mortandad (2% compra + 1% var.) $63,35 + Costos Fijos $33,60 = Costo Total $3.581,50 USD/cab / 3) Finishing Yearling Heifers (Maíz+Heno): Compra (700 lb a $3,74/lb) $2.618,00 + Interés (270 d) $137,69 + Alimentación $548,80 + Sanidad $8,00 + Maquinaria $11,20 + Comercialización $16,00 + Interés var. $15,57 + Mano de obra (2 h) $40,00 + Mortandad $30,75 + Costos Fijos $25,60 = Costo Total $3.451,62 USD/cab / 4) Backgrounding Invierno: Compra (450 lb a $4,92/lb) $2.214,00 + Interés (5 m) $65,59 + Alimentación $170,14 + Sanidad $5,00 + Maquinaria $7,20 + Comercialización $12,00 + Interés var. $2,88 + Mano de obra (1,25 h) $25,00 + Mortandad $23,91 + Fijos $22,40 = Costo Total $2.548,12 USD/cab / 5) Backgrounding Verano (Pastura): Compra (525 lb a $4,92/lb) $2.583,00 + Interés (5 m) $76,52 + Pastura/supl. $93,45 + Sanidad $5,00 + Maquinaria $6,80 + Comercialización $12,00 + Interés var. $1,74 + Mano de obra (1 h) $20,00 + Mortandad $27,29 + Fijos $3,36 = Costo Total $2.829,16 USD/cab | USD/cabeza | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 11-14)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 6. Precios por categoría | Novillos terminados (Iowa/Minnesota Choice Steers, all grades) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) en USD/cwt (1 cwt = 45,359 kg) | 2024: Ene 175,10 ($3,86/kg), Feb 181,24 ($4,00/kg), Mar 188,30 ($4,15/kg), Abr 185,47 ($4,09/kg), May 188,53 ($4,16/kg), Jun 195,31 ($4,31/kg), Jul 197,06 ($4,34/kg), Ago 190,56 ($4,20/kg), Sep 183,85 ($4,05/kg), Oct 188,68 ($4,16/kg), Nov 187,09 ($4,12/kg), Dic 193,82 ($4,27/kg) [Prom. 2024: 187,92 USD/cwt = $4,14/kg] / 2025: Ene 205,39 ($4,53/kg), Feb 203,35 ($4,48/kg), Mar 208,47 ($4,60/kg), Abr 215,00 ($4,74/kg), May 228,29 ($5,03/kg), Jun 237,25 ($5,23/kg), Jul 238,92 ($5,27/kg), Ago 243,58 ($5,37/kg), Sep 238,28 ($5,25/kg), Oct 235,40 ($5,19/kg), Nov 220,13 ($4,85/kg), Dic 225,76 ($4,98/kg) [Prom. 2025: 224,99 USD/cwt = $4,96/kg] | USD/cwt (y USD/kg vivo) | [Iowa State University Extension / USDA AMS LM_CT185 - File B2-12: Historical Cattle Prices (Pág. 1, Table 1, Feb 2026)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 |
| 6. Precios por categoría | Terneros de invernada (Iowa Medium & Large Frame #1, 500-600 lb Steers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026 | 2024 (USD/cwt): Ene 286,68 ($6,32/kg), Feb 309,77 ($6,83/kg), Mar 333,48 ($7,35/kg), Abr 324,06 ($7,14/kg), May 337,77 ($7,45/kg), Jun 320,30 ($7,06/kg), Jul 326,06 ($7,19/kg), Ago 300,50 ($6,62/kg), Sep 296,44 ($6,54/kg), Oct 296,60 ($6,54/kg), Nov 311,96 ($6,88/kg), Dic 332,23 ($7,32/kg) [Prom. 2024: 314,65 USD/cwt = $6,94/kg] / 2025 (USD/cwt): Ene 345,81 ($7,62/kg), Feb 353,55 ($7,79/kg), Mar 369,84 ($8,15/kg), Abr 375,34 ($8,27/kg), May 399,91 ($8,82/kg), Jun 408,30 ($9,00/kg), Jul 399,87 ($8,82/kg), Ago 449,83 ($9,92/kg), Sep 460,84 ($10,16/kg), Oct 454,61 ($10,02/kg), Nov 413,43 ($9,11/kg), Dic 446,07 ($9,83/kg) [Prom. 2025: 406,45 USD/cwt = $8,96/kg] / Presupuesto 2026 (File B1-21): $4,92/lb = 492,00 USD/cwt ($10,85/kg) | USD/cwt (y USD/kg vivo) | [ISU Extension / USDA-IA Dept of Ag Market News LSD_MARS_2167 - File B2-12 (Pág. 3, Table 3) y File B1-21 (Pág. 2)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 / 2026-06 |
| 6. Precios por categoría | Novillitos de recría (Iowa Medium & Large Frame #1, 700-800 lb Steers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026 | 2024 (USD/cwt): Ene 237,00, Feb 255,83, Mar 268,67, Abr 262,99, May 271,73, Jun 269,92, Jul 276,99, Ago 260,58, Sep 260,32, Oct 259,81, Nov 263,25, Dic 274,02 [Prom. 2024: 263,43 USD/cwt = $5,81/kg] / 2025 (USD/cwt): Ene 285,92, Feb 289,60, Mar 299,77, Abr 303,87, May 321,58, Jun 333,25, Jul 337,78, Ago 373,20, Sep 379,43 ($8,36/kg), Oct 375,15, Nov 339,48, Dic 363,28 [Prom. 2025: 333,53 USD/cwt = $7,35/kg] / Presupuesto 2026 (File B1-21): $3,74/lb = 374,00 USD/cwt ($8,25/kg) | USD/cwt (y USD/kg vivo) | [ISU Extension / USDA-IA Dept of Ag Market News - File B2-12 (Pág. 4, Table 4) y File B1-21 (Pág. 2)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 / 2026-06 |
| 6. Precios por categoría | Terneras 500-600 lb y Vaquillonas 700-800 lb (Iowa Medium & Large Frame #1 Heifers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026 | Heifers 500-600 lb (USD/cwt): 2024: Ene 244,74, Feb 269,36, Mar 285,18, Abr 286,62, May 296,66, Jun 285,94, Jul 281,76, Ago 275,62, Sep 272,85, Oct 268,82, Nov 275,13, Dic 298,93 (Prom. 278,47 = $6,14/kg); 2025: Ene 308,80, Feb 314,19, Mar 324,20, Abr 333,49, May 353,77, Jun 363,13, Jul 363,65, Ago 385,64, Sep 412,88 ($9,10/kg), Oct 395,67, Nov 366,18, Dic 392,13 (Prom. 359,48 = $7,93/kg); Presupuesto 2026 (400-500 lb): $4,84/lb = 484,00 USD/cwt ($10,67/kg) / Heifers 700-800 lb (USD/cwt): 2024: Ene 215,01, Feb 229,90, Mar 238,63, Abr 236,47, May 245,90, Jun 244,31, Jul 254,06, Ago 240,64, Sep 237,06, Oct 245,50, Nov 239,78, Dic 249,72 (Prom. 239,75 = $5,29/kg); 2025: Ene 259,83, Feb 263,22, Mar 269,11, Abr 272,79, May 288,99, Jun 299,56, Jul 316,14, Ago 342,27, Sep 347,22 ($7,65/kg), Oct 343,83, Nov 314,98, Dic 328,99 (Prom. 303,91 = $6,70/kg) | USD/cwt (y USD/kg vivo) | [ISU Extension / USDA-IA Dept of Ag Market News - File B2-12 (Pág. 5-6, Tables 5 & 6) y File B1-21 (Pág. 2)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 / 2026-06 |
| 6. Precios por categoría | Vacas de descarte (Breaking Utility Cows, 75-80% lean, Joplin MO / Midwest) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) | 2024 (USD/cwt): Ene 102,35, Feb 109,15, Mar 125,17, Abr 129,09, May 130,51, Jun 137,90, Jul 141,14 ($3,11/kg), Ago 139,81, Sep 125,56, Oct 120,51, Nov 114,28, Dic 111,60 [Prom. 2024: 123,92 USD/cwt = $2,73/kg] / 2025 (USD/cwt): Ene 126,22, Feb 135,97, Mar 136,10, Abr 143,00, May 146,81, Jun 153,02, Jul 157,07, Ago 166,39 ($3,67/kg), Sep 163,47, Oct 158,45, Nov 153,11, Dic 154,03 [Prom. 2025: 149,47 USD/cwt = $3,30/kg] / Serie mensual de 24 meses para vientre preñado (bred cow/heifer): SIN FUENTE (en File B1-21 de junio 2026 se valúa la vaca de cría y la vaquillona preñada de reposición en $2.300,00 USD/cabeza) | USD/cwt y USD/cabeza | [ISU Extension / USDA Market News - File B2-12 (Pág. 2, Table 2) y File B1-21 (Pág. 16)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 / 2026-06 |
| 6. Precios por categoría | Estacionalidad de precios por categoría en Iowa (2024-2025) | Novillos terminados (Choice steers): pico en julio-agosto ($197,06/cwt en jul-2024, +4,9% sobre media anual; $243,58/cwt en ago-2025, +8,3% sobre media anual) y piso en enero o septiembre / Vacas de descarte (Utility cows): pico en julio-agosto ($141,14/cwt en jul-2024, +13,9% sobre media; $166,39/cwt en ago-2025, +11,3% sobre media) y piso en noviembre-enero por el descarte otoñal post-destete / Terneros 500-600 lb y feeders 700-800 lb: picos en mayo (salida a pasto: $337,77/cwt en may-2024, +7,3% sobre media) y agosto-septiembre ($460,84/cwt en sep-2025, +13,4% sobre media), con bache estacional en octubre-noviembre durante el pico de oferta de destete | USD/cwt y % sobre media anual | [Iowa State University Extension - Ag Decision Maker File B2-12 (Pág. 1-6)](https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf) | 2026-02 |
| 7. Capital | Valor de una vaca de cría, un toro y un ternero de invernada, y capital inmovilizado por actividad en Iowa (2026) | Vaca de cría (beef cow): $2.300,00 USD/cab / Vaquillona de reposición: $2.300,00 USD/cab ($460,00 por unidad vaca al 20%) / Toro reproductor: $5.000,00 USD/cab ($200,00 por unidad vaca a 1 toro/25 vacas) -> Inversión total en rodeo por unidad vaca: $2.960,00 USD + Instalaciones/maquinaria/alambrados (rodeo de 50 vacas): $749,00 USD/vaca = $3.709,00 USD/unidad vaca inmovilizados en forma permanente (12 meses/año, más $698,98 de costos variables por 6 meses) / Ternero de invernada: 450 lb = $2.214,00 USD/cab; 525 lb = $2.583,00 USD/cab; 550 lb = $2.706,00 USD/cab (a $4,92/lb) / Novillito yearling (750 lb a $3,74/lb): $2.805,00 USD/cab / Vaquillona yearling (700 lb a $3,74/lb): $2.618,00 USD/cab / Capital operativo y tiempos de inmovilización: Backgrounding invierno $2.525,72 var. (5 meses hacienda / 2,5 meses var.); Backgrounding verano $2.825,80 var. (5 meses / 2,5 meses); Finishing Yearling Steers $3.445,74 var. (6,5 meses hacienda / 3,25 meses var.); Finishing Steer Calves $3.547,90 var. (9 meses hacienda / 4,5 meses var.); Finishing Yearling Heifers $3.426,02 var. (270 días hacienda / 4,5 meses var.) a una tasa de interés operativo del 7,11% anual | USD/cabeza y meses | [Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 2, 11-16)](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf) | 2026-06 |
| 8. Impuestos, retenciones o tasas | Tasas e impuestos sobre la hacienda y las instalaciones ganaderas en Iowa / EE.UU. | National Beef Checkoff (federal): $1,00 USD por cabeza en cada venta de ganado bovino vivo doméstico o importado / Derechos de exportación (retenciones): 0% (no existen en EE.UU.) / Impuestos a la propiedad y seguros sobre instalaciones y equipos (Taxes & Insurance en presupuestos ISU): 1% anual sobre el valor de inversión original de instalaciones y equipos (dentro del 14% anual de cargo fijo = 8% depreciación + 5% interés + 1% impuestos y seguros) | USD/cabeza y % anual | [Cattlemen's Beef Board / USDA AMS y ISU Extension File B1-21 (Pág. 1)](https://www.beefboard.org/2024/07/09/new-independent-study-finds-each-national-beef-checkoff-dollar-returns-13-41/) | 2024-07 / 2026-06 |
| 9. Riesgos | Riesgos climáticos y nutricionales en Iowa y respuestas del productor | Riesgos: inviernos con nieve/hielo y temperaturas bajo cero (sin crecimiento de pasturas entre noviembre y abril), sequías estivales que reducen la receptividad de las pasturas de gramíneas templadas (bluegrass/bromegrass) y estrés post-destete en terneros / Respuestas documentadas: 1) Pastoreo de rastrojos de maíz en otoño-invierno (4 acres/vaca con 3.467 lb MO/acre) y reserva de 2,1 tons/vaca de heno alfalfa-brome; 2) Preacondicionamiento y destete anticipado (early weaning de terneros de 300-500 lb) con dietas de recepción de 65-75% concentrado y 14,5% proteína bruta; 3) Sustitución entre grano de maíz, silaje de maíz y granos de destilería (MDGS/DDGS, donde 1 lb de MDGS reemplaza la energía de 0,5 lb de maíz y la proteína de 0,36 lb de harina de soja); 4) Pastoreo rotativo (+25% de producción forrajera) o envío directo de terneros a backgrounding/feedlot en confinamiento | estrategia técnica | [ISU Extension File B1-21 (Pág. 11-15), File C2-23 (Pág. 2), ASL-1636 e Iowa Beef Center (Nutritional Management of the Calf after Weaning)](https://www.iowabeefcenter.org/Health/nutritionafterweaning.pdf) | 2025-08 / 2026-06 |

## C. Lista consolidada de datos que quedaron "SIN FUENTE"

- **Zonas 1, 2 y 3 (Argentina) — Serie completa mes a mes de los últimos 24 meses para las 6 categorías (ternero, novillito, novillo, vaquillona, vaca, vientre preñado)**: `SIN FUENTE` en documentos abiertos para los 24 meses continuos. Los boletines trimestrales de SAGyP ([Boletín N° 59, Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf)) presentan la evolución mensual en gráficos índice, mientras que los Tableros de Precios Bovinos ([Agosto 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20AGOSTO%202026.pdf) y [Septiembre 2026](https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf)) y la web de [Rosgan](https://rosgan.com.ar/indices) publican en texto extraíble los valores puntuales de agosto y septiembre (2022 a 2026).
- **Zonas 1, 2 y 3 (Argentina) — Cuadros detallados de costos por cabeza y capital inmovilizado en ARS de 2026**: `SIN FUENTE` para el desagregado numérico ítem por ítem en 2026, debido a que en los Boletines N° 57, 58 y 59 de 2026 de SAGyP las planillas individuales de cada modelo están incrustadas como imágenes rasterizadas sin texto seleccionable (se reportan los márgenes brutos actualizados a 2026 del texto del Boletín N° 59 y los coeficientes físicos/proporciones de las tablas vectoriales del [Boletín N° 10 de SAGyP](https://www.google.com/search?q=https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%25C3%25ADn%2520trimestral/000019-2014/120609_Bolet%25C3%25ADn%25C2%25B0%252010%2520-%2520JUNIO%25202014.pdf)).
- **Zonas 1, 2 y 3 (Argentina) — Costo monetario por dosis de vacunas (aftosa, brucelosis, mancha/gangrena, carbunclo) y valor exacto en ARS de 2026 del arancel DT-e de SENASA y guías municipales**: `SIN FUENTE` en las resoluciones técnicas abiertas consultadas ([SENASA Disposición 21/2026](https://www.argentina.gob.ar/normativa/nacional/norma-426404/texto) y [Disposición 27/2026](https://www.argentina.gob.ar/noticias/vacunacion-antiaftosa-procedimientos-para-la-libre-eleccion-de-veterinarios-acreditados)).
- **Zona 1 (Cuenca del Salado, Argentina) — Parámetros de invernada pura a pasto y engorde a corral puro, y edad exacta de descarte en años**: `SIN FUENTE` (SAGyP clasifica la región como netamente criadora y no modela invernada pura ni feedlot en ella; para descarte de vientres las fuentes técnicas de INTA/UNRC reportan una tasa de refugo por vejez del 6% anual del rodeo en lugar de una edad fija en años).
- **Zona 3 (Zona Núcleo / Pergamino, Argentina) — Modelo oficial de cría vacuna**: `SIN FUENTE` (SAGyP explicita en la pág. 82 del [Boletín N° 59](https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf) que no confecciona modelos de cría para el Norte de Buenos Aires por ser la agricultura la actividad principal).
- **Zona 4 (Mato Grosso, Brasil) — Serie completa mes a mes de los últimos 24 meses para las 6 categorías, precio de vientre preñado (vaca/novilha prenhe), conversión alimenticia de corral en 2026 y producción estacional de MS (kg MS/ha en las 4 estaciones)**: `SIN FUENTE` en los boletines abiertos semanales de [IMEA](https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911) y capítulos técnicos de [Embrapa Gado de Corte](https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf) (que informan acumulados de diferimiento de 4.000 a 8.000 kg MS/ha y series trimestrales/semanales recientes).
- **Zona 5 (Iowa / Midwest, EE.UU.) — % de preñez explícito (se publica directamente 92% de destete), desagregado estacional trimestral de producción de pasturas en kg MS/ha (se publica producción anual en ton/acre y AUM/acre en File C2-23) y serie mensual de 24 meses para vientre preñado (se publica el valor de capital de $2.300 USD/cabeza en File B1-21)**: `SIN FUENTE` en las publicaciones abiertas de [Iowa State University Extension Ag Decision Maker](https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf).

## D. Bloque JSON estructurado por zona

```json
[
  {
    "zona": "1. Cuenca del Salado (provincia de Buenos Aires, Argentina)",
    "datos": [
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría modal y mejorada - Categoría que entra y que sale",
        "valor": "Entra: Vaquillona de reposición propia (1° servicio a los 27 meses) y Toro de compra (650 kg) | Sale: Ternero destete, Ternera destete, Vaca gorda (447 kg), Vaca conserva (380 kg) y Toro rechazo (570 kg)",
        "unidad": "categoría",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Modelos Cría Cuenca del Salado)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría modal - Peso de salida ternero macho / ternera hembra al destete",
        "valor": "175 (macho) / 170 (hembra)",
        "unidad": "kg/cabeza",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría mejorada - Peso de salida ternero macho / ternera hembra al destete",
        "valor": "180 (macho) / 160 (hembra)",
        "unidad": "kg/cabeza",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 10)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría - Duración de lactancia hasta destete y meses típicos de servicio, parición y venta",
        "valor": "Duración: 6 a 8 meses de lactancia | Servicio: octubre-diciembre (o noviembre-enero) | Parición: julio-septiembre | Venta terneros: marzo-abril",
        "unidad": "meses",
        "fuente": "INTA EEA Cuenca del Salado - Estado de situación en la Cuenca del Salado (Pág. 2) y SAGyP Boletín N° 10 (Pág. 9)",
        "link": "http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf",
        "fecha": "2019-10"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Recría corta post-destete en campo de cría - Categoría, pesos, duración y mes de venta",
        "valor": "Entra: Ternero (175 kg) y Ternera (170 kg) en marzo | Sale: Ternero recriado (250 kg) y Ternera recriada (240 kg) en junio-julio | Duración: 4 meses",
        "unidad": "kg/cabeza y meses",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 24)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Engorde a pasto (invernada pura) y Engorde a corral puro en Cuenca del Salado",
        "valor": "SIN FUENTE (SAGyP clasifica a la Cuenca del Salado con relación novillo/vaca de 0,07 y N+N/vaca de 0,13 como zona netamente de cría y no modela invernada pura ni feedlot puro dentro de esta subregión)",
        "unidad": "SIN FUENTE",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 82-83)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "2. Cría",
        "dato": "% de preñez (rodeos monitoreados y módulo agroecológico INTA Cuenca del Salado)",
        "valor": ">92 (módulo INTA Cuenca del Salado) / 92,5 (promedio 10 años establecimiento Cuenca del Salado)",
        "unidad": "%",
        "fuente": "UNICEN / INTA - Planificación forrajera en la Cuenca del Salado (Pág. 20) y Valor Carne / INTA EEA Cuenca del Salado",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "2. Cría",
        "dato": "% de destete (Cría Chica / Cría Modal / Cría Mejorada en Cuenca del Salado)",
        "valor": "70 (Chica) / 72 (Modal) / 80 (Mejorada) [rango regional INTA EEA Cuenca del Salado: 70 a 90]",
        "unidad": "%",
        "fuente": "SAGyP - Boletín Trimestral N° 10 (Pág. 9-11) e INTA EEA Cuenca del Salado (Pág. 2)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "2. Cría",
        "dato": "% de mortandad y pérdidas reproductivas (preñez-parto y mortandad anual de vientres)",
        "valor": "6% pérdida preñez-parición y 3% mortandad anual de vacas adultas (2% mortandad + 3% refugo sanitario en vacas; 4% mortandad en terneras de reposición; 5% en vaquillonas 2° servicio)",
        "unidad": "%",
        "fuente": "Sitio Argentino de Producción Animal / INTA Balcarce (Equivalencias Ganaderas, Pág. 2) y UNICEN (Pág. 52)",
        "link": "https://www.produccion-animal.com.ar/produccion_y_manejo_pasturas/pastoreo%20sistemas/70-equivalencias_ganaderas.pdf",
        "fecha": "2006 / 2020-11 (dato más viejo)"
      },
      {
        "tema": "2. Cría",
        "dato": "% de reposición anual de vientres (Cría Chica / Cría Modal / Cría Mejorada)",
        "valor": "18 (Chica) / 22 (Modal) / 23 (Mejorada)",
        "unidad": "%",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "2. Cría",
        "dato": "Edad al primer servicio de vaquillonas y edad de descarte",
        "valor": "Edad al 1° servicio: 27 meses (SAGyP modal/mejorada) o 15 meses (sistema intensificado) | Edad exacta de descarte en años: SIN FUENTE (se reporta descarte por vejez del 6% anual del rodeo)",
        "unidad": "meses / %",
        "fuente": "SAGyP - Boletín Trimestral N° 10 (Pág. 9-10) e INTA Equivalencias Ganaderas (Pág. 2)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "2. Cría",
        "dato": "Toros cada 100 vacas (porcentaje de toros en modelos Cuenca del Salado)",
        "valor": "4 (Modal y Mejorada) / 5 (Chica)",
        "unidad": "toros/100 vacas (%)",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad / Carga animal media anual en Cuenca del Salado",
        "valor": "0,37 (Cría Chica) / 0,56 (Cría Modal) / 0,70 (umbral seguro campo natural INTA) / 0,91 (Cría Mejorada)",
        "unidad": "EV/ha",
        "fuente": "SAGyP - Boletín Trimestral N° 10 (Pág. 9-11) e INTA EEA Cuenca del Salado (Pág. 4)",
        "link": "http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf",
        "fecha": "2019-10"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad mensual/estacional del campo natural en Cuenca del Salado",
        "valor": "Otoño: Mar 0,8, Abr 0,6, May 0,3 | Invierno: Jun 0,3, Jul 0,3, Ago 0,3 | Primavera: Sep 0,6, Oct 1,2, Nov 1,2 | Verano: Dic 1,0, Ene 0,6, Feb 0,8",
        "unidad": "EV/ha/día",
        "fuente": "UNICEN / Tablas Equivalencias CREA-INTA (Pág. 48)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Producción anual de forraje de campo natural en Cuenca del Salado (Gral. Alvear) según fertilización fosforada",
        "valor": "3.891 (sin fertilizar, 0 kg P/ha: 613 kg MS pastos OIP anuales, 68 kg MS OIP perennes, 1.895 kg MS pastos PEO estivales, 25 kg MS leguminosas, 1.290 kg MS malezas) | 5.478 (con 29 kg P/ha) | 7.814 (con 66 kg P/ha)",
        "unidad": "kg MS/ha/año",
        "fuente": "UNICEN / Rodríguez et al. (Pág. 35, Tabla 8)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Producción de forraje de pastura de festuca templada diferida en otoño (marzo a junio)",
        "valor": "3.330 acumulados (Marzo: 36 kg MS/ha/día = 1.080 kg MS/ha; Abril: 38 kg MS/ha/día = 1.140 kg MS/ha; Mayo: 27 kg MS/ha/día = 810 kg MS/ha; Junio: 10 kg MS/ha/día = 300 kg MS/ha; con 65% eficiencia de cosecha = 2.164,5 kg MS/ha consumidos)",
        "unidad": "kg MS/ha",
        "fuente": "UNICEN / Cangiano y Brizuela INTA (Pág. 50)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Producción de forraje en kg MS/ha por estación de verdeos en Cuenca del Salado",
        "valor": "SIN FUENTE en kg MS/ha por estación (las tablas zonales expresan la oferta mensual en raciones o EV/ha/día; ver Zona 2 para raciones mensuales de avena y sorgo)",
        "unidad": "SIN FUENTE",
        "fuente": "UNICEN (Pág. 39-40, 48)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Consumo diario de un Equivalente Vaca (EV)",
        "valor": "18,54 Mcal EM/día, equivalentes a: 11,384 kg MS/día (50% digestibilidad), 10,078 kg MS/día (60% digestibilidad), 8,003 kg MS/día (70% digestibilidad) o 10,0 kg MS/día como valor práctico de presupuestación",
        "unidad": "kg MS/EV/día (y Mcal EM/día)",
        "fuente": "UBA FCV / INTA Balcarce - Texto de Estudio Carga Animal y Sistemas de Pastoreo (Pág. 5 y 14) y UNICEN (Pág. 50)",
        "link": "http://dpd.fvet.uba.ar/cartelera/00030355.pdf",
        "fecha": "2020 (dato más viejo)"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Parámetros de conversión y costo de ración de corral en Cuenca del Salado",
        "valor": "SIN FUENTE específica para Cuenca del Salado (los parámetros de engorde a corral y recría+corral de SAGyP se modelan para Zona Núcleo/Oeste; ver Zonas 2 y 3)",
        "unidad": "SIN FUENTE",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 58-66)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Sanidad obligatoria SENASA (vacunación antiaftosa y brucelosis)",
        "valor": "Fiebre aftosa (2 campañas anuales en menores/según estrategia Resolución SENASA 711/2025 y Disp. 21/2026) y Brucelosis (terneras de 3 a 8 meses) | Costo monetario por dosis de vacuna en 2026: SIN FUENTE",
        "unidad": "calendario oficial",
        "fuente": "SENASA - Disposición 21/2026 y Disposición 27/2026",
        "link": "https://www.argentina.gob.ar/normativa/nacional/norma-426404/texto",
        "fecha": "2026-06"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Costos directos e indirectos históricos en Cría Modal Cuenca del Salado (450 ha, 260 vacas)",
        "valor": "Personal: 120 ARS/cab (154 ARS/vientre, 89 ARS/ha) | Sanidad: 78 ARS/cab (100 ARS/vientre, 58 ARS/ha) | Alimentación: 24 ARS/cab (30 ARS/vientre, 18 ARS/ha) | Estructura e impuestos: 426 ARS/cab (549 ARS/vientre, 317 ARS/ha) | Amortizaciones: 101 ARS/cab (75 ARS/ha) | Total: 748 ARS/cab (557 ARS/ha)",
        "unidad": "ARS de 2014-05 (y proporción: 57% estructura, 16% personal, 14% amort., 10% sanidad, 3% alim.)",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Dotación de mano de obra y salario mensual de peón ganadero (2026)",
        "valor": "1 peón cada 600 vientres (mínimo 0,5 Equivalente Hombre por establecimiento) | Salario mensual: 789 USD/mes (1.230.840 ARS/mes al TC BNA de 1.560 ARS/USD del 31/10/2026)",
        "unidad": "USD/mes y ARS/mes",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76 y 86)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-08"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Precio del gasoil para labores y fletes (2026)",
        "valor": "1,18 USD/litro (1.840,80 ARS/litro al TC BNA de 1.560 ARS/USD del 31/10/2026)",
        "unidad": "USD/litro y ARS/litro",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-08"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Gastos de comercialización (comisión + flete + tasas) y desbaste en Cría Cuenca del Salado",
        "valor": "Gastos de comercialización: 6,80% (Modal), 6,78% (Mejorada), 6,75% (Chica) sobre ventas brutas | Desbaste: 5%",
        "unidad": "%",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 9-11)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Margen bruto de Cría Cuenca del Salado (Modelo base actualizado a 2026)",
        "valor": "317.750 ARS/ha (203,69 USD/ha al TC oficial BNA venta de 1.560,00 ARS/USD del 31/10/2026)",
        "unidad": "ARS/ha y USD/ha",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 67)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Ternero de invernada (Cuenca del Salado) - Agosto y Septiembre 2025 vs. Agosto y Septiembre 2026",
        "valor": "Ago-2025: 5.343 ARS/kg constante | Sep-2025: 5.640 ARS/kg constante | Ago-2026: 6.557 ARS/kg (4,20 USD/kg) | Sep-2026: 6.572 ARS/kg (4,21 USD/kg al TC BNA 1.560 ARS/USD)",
        "unidad": "ARS/kg vivo y USD/kg vivo",
        "fuente": "SAGyP - Tablero de Precios Bovinos Agosto y Septiembre 2026",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Liviano consumo (novillitos y vaquillonas hasta 390 kg) y Novillo pesado (+430 kg) - Septiembre 2026",
        "valor": "Liviano hasta 390 kg: 4.613 ARS/kg (2,96 USD/kg) en Sep-2026 y 4.834 ARS/kg (3,10 USD/kg) en Ago-2026 | Novillo +430 kg: 4.275 ARS/kg (2,74 USD/kg) en Sep-2026 y 4.414 ARS/kg (2,83 USD/kg) en Ago-2026 (TC BNA 1.560 ARS/USD)",
        "unidad": "ARS/kg vivo y USD/kg vivo",
        "fuente": "SAGyP - Tablero de Precios Bovinos Agosto y Septiembre 2026",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Índices Rosgan de Invernada y Cría - Septiembre 2026",
        "valor": "Terneros: 6.135,40 ARS/kg (3,93 USD/kg) | Terneras: 5.813,33 ARS/kg (3,73 USD/kg) | Terneros/as: 6.027,85 ARS/kg (3,86 USD/kg) | Novillos 1-2 años: 5.329,43 ARS/kg (3,42 USD/kg) | Novillos 2-3 años: 4.551,10 ARS/kg (2,92 USD/kg) | Vaquillonas invernada: 5.094,98 ARS/kg (3,27 USD/kg) | Vacas invernada: 3.221,24 ARS/kg (2,06 USD/kg) | PIRI general: 5.537,82 ARS/kg (3,55 USD/kg) (TC BNA 1.560 ARS/USD)",
        "unidad": "ARS/kg vivo y USD/kg vivo",
        "fuente": "Rosgan - Índices de Precios Anuales Septiembre 2026",
        "link": "https://rosgan.com.ar/indices",
        "fecha": "2026-09"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Relación vaquillona preñada / vaca conserva y relación ternero / novillo (2026)",
        "valor": "1 vaquillona preñada = 2,59 vacas conserva de ~400 kg (promedio histórico 10 años = 2,06) | Relación ternero/novillo = 1,46 (máximo anual en mayo 2026) | Relación ternero/novillito = 1,28 | Serie completa de los 24 meses mes a mes para las 6 categorías en Argentina: SIN FUENTE en tablas abiertas (los boletines publican gráficos de evolución y los tableros mensuales reportan el mes en curso y la comparación interanual de agosto y septiembre)",
        "unidad": "relación de precios",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 3, 71-72)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "7. Capital",
        "dato": "Valor de un ternero de invernada (175 kg) y de una vaca de invernada/cría (400 kg) en 2026",
        "valor": "Ternero 175 kg (Cuenca del Salado a 6.572 ARS/kg): 1.150.100 ARS/cabeza (737,24 USD/cab) | Vaca de invernada 400 kg (Rosgan a 3.221,24 ARS/kg): 1.288.496 ARS/cabeza (825,96 USD/cab) | Vaquillona preñada (2,59 vacas de 400 kg): ~3.337.205 ARS/cabeza (2.139,23 USD/cab) al TC BNA 1.560 ARS/USD",
        "unidad": "ARS/cabeza y USD/cabeza",
        "fuente": "SAGyP Tablero Septiembre 2026, Boletín N° 59 (Pág. 72) y Rosgan Septiembre 2026",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "7. Capital",
        "dato": "Monto total de capital inmovilizado por hectárea actualizado a 2026",
        "valor": "SIN FUENTE del monto absoluto en ARS de 2026 (las hojas detalladas de los modelos en el Boletín N° 59 están insertadas como imágenes sin texto extraíble; en el Boletín N° 10 de 2014-05 la rentabilidad sobre capital sin tierra era 10,9% en cría modal y 12,8% en cría mejorada, con inmovilización permanente de 12 meses en cría y 4 meses en recría corta)",
        "unidad": "% y meses",
        "fuente": "SAGyP - Boletín Trimestral N° 10 (Pág. 9-10, 24) y Boletín N° 59 (Pág. 8-10)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "Derechos de exportación (retenciones) e IVA sobre hacienda y carne bovina en Argentina",
        "valor": "Derechos de exportación categoría vaca (cortes tipos A, B, C, D y E, excepto animales vivos): 0% (eliminados por Decreto 697/2024) | Resto de cortes bovinos: reducción del 25% sobre alícuota previa del 9% (= 6,75%) | IVA sobre venta de hacienda bovina en pie y carnes: 10,5% (Art. 28 Ley de IVA) | Valor monetario exacto de tasa de guía municipal y arancel DT-e SENASA en 2026: SIN FUENTE",
        "unidad": "%",
        "fuente": "Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI - Tratamiento Impositivo de la Actividad Ganadera",
        "link": "https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer",
        "fecha": "2024-08"
      },
      {
        "tema": "9. Riesgos",
        "dato": "Riesgos climáticos (sequía e inundación) y decisiones de manejo del productor en Cuenca del Salado",
        "valor": "Riesgos: inundaciones periódicas por suelos planos de baja permeabilidad (VIws) y sequías de salida de invierno-primavera (mayo-septiembre) | Respuestas documentadas: 1) Clasificar potreros y rodeos por Estado Corporal (EC crítico = 3 en escala 1-5); 2) Venta de animales improductivos y vacas vacías; 3) Destete anticipado o precoz (o ecografía ovárica en diciembre para destetar solo vacas en anestro); 4) Adelantar servicio en lotes con EC >= 3 y suplementar priorizando vacas de 1° parición > multíparas > vaquillonas",
        "unidad": "estrategia técnica",
        "fuente": "INTA EEA Cuenca del Salado - Estado de situación en la Cuenca del Salado (Pág. 2-7)",
        "link": "http://produccionforrajes.org.ar/wp-content/uploads/2019/10/informe-de-situacion-y-recomendaciones-ganaderas-ante-la-situacion-climatica-eea-cuenca-del-salado-octubre-2019-0.pdf",
        "fecha": "2019-10"
      }
    ]
  },
  {
    "zona": "2. Azul / centro de la provincia de Buenos Aires",
    "datos": [
      {
        "tema": "1. Actividades habituales",
        "dato": "Ciclo completo con terminación a corral (Establecimiento en Azul, 1.451 ha) - Categorías, pesos, duración y meses",
        "valor": "Cría: servicio oct-dic (entore 15 meses), destete en marzo con 160 kg (hembras) y 180 kg (machos) | Recría y engorde machos: 180 a 400 kg en 10-11 meses (ADPV 0,75 kg/día; pasturas/verdeos mar-nov, maíz verdeo dic-ene, corral terminación, venta dic 50%, ene 30%, feb 20%) | Recría y engorde hembras: 160 a 375 kg en 11 meses (ADPV 0,65 kg/día; venta fines ene-feb) | Engorde vacas vacías/viejas a corral: 2 meses (abril-mayo, ADPV 0,75 kg/día, +45 kg/cab, venta fines de mayo)",
        "unidad": "kg/cabeza, meses y kg/día",
        "fuente": "UNICEN - Planificación forrajera para un establecimiento agrícola-ganadero en el partido de Azul (Pág. 26-27, 52-54)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Ciclo Completo Centro-Sudoeste Buenos Aires (modelo oficial SAGyP, 380 ha ganaderas) - Categorías y pesos de venta",
        "valor": "Destete a los 8 meses (ternero 180 kg, ternera 170 kg) | Venta de Vaquillonas recría/engorde: 295 kg | Venta de Novillos invernada: 390 kg | Venta de Vacas gordas: 447 kg | Venta de Vacas conserva: 380 kg | Venta de Toros rechazo: 570 kg (Compra toros: 650 kg)",
        "unidad": "kg/cabeza",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 31)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "2. Cría",
        "dato": "% de preñez, % de destete, % de reposición y edad al 1° servicio (Establecimiento en Azul vs. Modelo SAGyP Centro-SO)",
        "valor": "Azul (promedio 10 años): Preñez 92,5%, Destete 86%, Reposición anual de vientres 20%, Reposición anual de toros 20%, 1° servicio 15 meses | Modelo SAGyP Centro-SO: Destete 69%, Reposición 20%, 1° servicio 24 meses",
        "unidad": "% y meses",
        "fuente": "UNICEN (Pág. 20, 52-53) y SAGyP Boletín N° 10 (Pág. 31)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "2. Cría",
        "dato": "% de mortandad y refugo por categoría en Azul",
        "valor": "Vacas generales y vaquillonas 1° servicio: 2% mortandad + 3% refugo sanitario pre-servicio | Vaquillonas 2° servicio: 5% mortandad | Terneras de reposición: 4% mortandad (marzo-septiembre)",
        "unidad": "%",
        "fuente": "UNICEN - Planificación forrajera en el partido de Azul (Pág. 52-53)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "2. Cría",
        "dato": "Toros cada 100 vacas en Azul / Centro-Sudoeste",
        "valor": "4,0 (Modelo SAGyP Centro-SO) a 4,6 (Establecimiento Azul: 35 toros sobre 754 vacas generales, o 3,6 toros cada 100 vientres totales incluyendo vaquillonas)",
        "unidad": "toros/100 vacas (%)",
        "fuente": "SAGyP Boletín N° 10 (Pág. 31) y UNICEN (Pág. 30)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad y carga animal en Azul y Centro-Sudoeste",
        "valor": "Establecimiento Azul (1.451 ha): 1.466,68 EV totales = 1,01 EV/ha (1,25 cab/ha) | Modelo SAGyP Centro-SO (380 ha): 0,50 vacas/ha, 0,93 cab/ha, 323 kg PV/ha, producción de carne 117,2 kg/ha/año",
        "unidad": "EV/ha y cab/ha",
        "fuente": "UNICEN (Pág. 19, 30) y SAGyP Boletín N° 10 (Pág. 31)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Oferta forrajera mensual por recurso en zona Centro-Sudeste / Balcarce (en raciones/ha/mes = EV·día/ha/mes)",
        "valor": "Campo natural (288 rac/ha/año): Ene 24, Feb 24, Mar 24, Abr 24, May 12, Jun 12, Jul 12, Ago 12, Sep 24, Oct 42, Nov 42, Dic 36 | Pastura base Alfalfa (672 rac/ha/año): Ene 66, Feb 48, Mar 54, Abr 42, May 24, Jun 24, Jul 24, Ago 30, Sep 30, Oct 105, Nov 108, Dic 117 | Pastura en implantación (195 rac/ha): Ago 30, Sep 45, Oct 45, Nov 45, Dic 30 | Verdeo Avena (489 rac/ha): Mar 30, Abr 60, May 45, Jun 60, Jul 60, Ago 60, Sep 72, Oct 72, Nov 30 | Verdeo Sorgo pastoreo (363 rac/ha): Dic 111, Ene 111, Feb 111, Mar 30",
        "unidad": "raciones (EV·día)/ha/mes",
        "fuente": "UBA FCV / INTA EEA Balcarce - Texto de Estudio Carga Animal y Sistemas de Pastoreo (Pág. 8, Tabla 1)",
        "link": "http://dpd.fvet.uba.ar/cartelera/00030355.pdf",
        "fecha": "2020 (dato más viejo)"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Equivalencias forrajeras de granos y silajes utilizados en Azul",
        "valor": "Grano de maíz: 154 EV/tonelada | Grano de cebada: 152 EV/tonelada (rinde zonal estimado: 4.000 kg/ha) | Silo de planta entera de maíz (30% MS): 50 EV/tonelada de MS | Consumo por EV: 10 kg MS/día (18,54 Mcal EM/día)",
        "unidad": "EV/t y kg MS/EV/día",
        "fuente": "UNICEN - Planificación forrajera en el partido de Azul (Pág. 48-50)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Acumulación primaveral de pastizal natural con fertilización nitrogenada (INTA Balcarce / Pampa Deprimida)",
        "valor": "Corte al 04/11: 2.433,2 kg MS/ha (0 kg N/ha) | 5.074,0 kg MS/ha (50 kg N/ha) | 5.700,2 kg MS/ha (100 kg N/ha) | 6.986,4 kg MS/ha (150 kg N/ha) | 6.995,9 kg MS/ha (200 kg N/ha) | 7.114,4 kg MS/ha (250 kg N/ha)",
        "unidad": "kg MS/ha",
        "fuente": "UNICEN / Fernández Grecco y Agnusdei INTA Balcarce (Pág. 36, Tabla 9)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Aumento diario de peso (ADPV) por categoría en Azul y modelo Centro-Sudoeste",
        "valor": "Terneros/novillitos en recría-invernada: 0,75 kg/día | Terneras de invernada: 0,65 kg/día | Terneras y vaquillonas de reposición: 0,50 kg/día | Toritos 1 año: 1,20 kg/día | Vacas vacías/viejas en corral de engorde (60 días): 0,75 kg/día | Conversión alimenticia y costo por kg de ración en Azul: SIN FUENTE (ver modelo de recría y corral de SAGyP en Zona 3)",
        "unidad": "kg/día",
        "fuente": "UNICEN - Planificación forrajera en el partido de Azul (Pág. 52-54)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Costos directos e indirectos en Ciclo Completo Centro-Sudoeste Buenos Aires (380 ha, 190 vacas)",
        "valor": "Personal: 338 ARS/cab (626 ARS/vientre, 313 ARS/ha; 24% del costo total) | Sanidad: 97 ARS/cab (179 ARS/vientre, 90 ARS/ha; 7%) | Alimentación: 337 ARS/cab (623 ARS/vientre, 312 ARS/ha; 24%) | Estructura e impuestos: 519 ARS/cab (959 ARS/vientre, 480 ARS/ha; 37%) | Amortizaciones: 118 ARS/cab (218 ARS/vientre, 109 ARS/ha; 8%) | Costo Total: 1.408 ARS/cab (1.303 ARS/ha) | Gastos comercialización: 7,5% | Desbaste: 4%",
        "unidad": "ARS de 2014-05 y %",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 31)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Precio de maíz e insumos operativos nacionales en 2026",
        "valor": "Maíz: 178 USD/t (277.680 ARS/t) | Salario peón: 789 USD/mes (1.230.840 ARS/mes) | Gasoil: 1,18 USD/litro (1.840,80 ARS/litro) al TC oficial BNA de 1.560 ARS/USD del 31/10/2026",
        "unidad": "USD y ARS",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 76)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-08"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Precios de referencia de hacienda aplicables a Buenos Aires (Septiembre 2026)",
        "valor": "Ternero invernada: 6.572 ARS/kg (4,21 USD/kg) | Liviano consumo hasta 390 kg: 4.613 ARS/kg (2,96 USD/kg) | Novillo pesado +430 kg: 4.275 ARS/kg (2,74 USD/kg) | Vaca invernada (Rosgan): 3.221,24 ARS/kg (2,06 USD/kg) al TC BNA 1.560 ARS/USD | Serie mensual completa de 24 meses por categoría: SIN FUENTE en publicaciones abiertas",
        "unidad": "ARS/kg vivo y USD/kg vivo",
        "fuente": "SAGyP Tablero Septiembre 2026 y Rosgan Septiembre 2026",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/informacion_sectorial/_archivos//000020_Tablero%20de%20precios%20bovinos/000001_Tablero%20PRECIOS%20BOVINOS%20SEPTIEMBRE%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "7. Capital",
        "dato": "Capital y tiempos de inmovilización en Ciclo Completo Centro-Sudoeste / Azul",
        "valor": "Vientres: 12 meses | Recría-engorde de machos propios: 10 a 11 meses (de marzo a dic/ene/feb) | Recría-engorde de hembras propias: 11 meses (marzo a ene/feb) | Engorde de vacas de refugo a corral: 2 meses (abril-mayo) | Rentabilidad histórica sobre capital sin tierra en modelo Centro-SO: 3,2%",
        "unidad": "meses y %",
        "fuente": "UNICEN (Pág. 52-54) y SAGyP Boletín N° 10 (Pág. 31)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "Régimen impositivo nacional sobre hacienda y carne (Argentina)",
        "valor": "Derechos de exportación carne de vaca (A-E): 0% (Decreto 697/2024) | Derechos de exportación resto carne bovina: 6,75% (reducción del 25% sobre 9%) | IVA hacienda bovina en pie: 10,5% | Tasas municipales de guía en Azul 2026: SIN FUENTE",
        "unidad": "%",
        "fuente": "Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI",
        "link": "https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer",
        "fecha": "2024-08"
      },
      {
        "tema": "9. Riesgos",
        "dato": "Riesgos climáticos y forrajeros en Azul y manejo del productor",
        "valor": "Déficits estacionales de forraje en invierno (agosto-septiembre, por heladas durante 239 días/año) y verano (noviembre-enero), además de anegamientos en suelos bajos | Respuestas: encierre a corral de terneros/as cola de parición (marzo-septiembre) con grano o silaje de maíz; diferimiento de maíz en pie y pasturas de festuca con rollos y silaje en autoconsumo para vacas en parición; rejuvenecimiento de agropiro y campo natural con fósforo/nitrógeno e implantación de raigrás anual y verdeos de verano (maíz/sorgo)",
        "unidad": "estrategia técnica",
        "fuente": "UNICEN - Planificación forrajera en el partido de Azul (Pág. 21, 26-28, 32-40)",
        "link": "https://www.ridaa.unicen.edu.ar/bitstreams/4831a3fe-bf5b-4b1b-a3be-581dcab1ff0a/download",
        "fecha": "2020-11"
      }
    ]
  },
  {
    "zona": "3. Zona núcleo (Pergamino, Argentina)",
    "datos": [
      {
        "tema": "1. Actividades habituales",
        "dato": "Invernada de Alta Producción (con suplementación, 500 ha) - Categorías, pesos y duración",
        "valor": "Entra: Ternero de 180 kg | Sale: Novillo de 404 kg | Duración: 11,5 meses (ADPV: 0,70 kg/día) | Meses de compra/venta: compra en otoño (zafra mar-may), venta a fines de verano/otoño siguiente",
        "unidad": "kg/cabeza y meses",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 34) y Boletín N° 59 (Pág. 43, 47)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Invernada de Media Producción (sin suplementación, 500 ha) e Invernada Santa Fe Centro (700 ha)",
        "valor": "Media Producción: Entra ternero 180 kg, Sale novillo 399 kg en 15,8 meses (ADPV 0,50 kg/día) | Santa Fe Centro: Entra ternero 180 kg, Sale novillo 427,5 kg en 22,2 meses (ADPV 0,40 kg/día)",
        "unidad": "kg/cabeza y meses",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 33, 35)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Recría a campo + Terminación a corral (consumo interno) y Engorde de novillo pesado a corral (exportación)",
        "valor": "Recría + Corral liviano: Entra ternero 180 kg a pasto hasta 300 kg, entra a corral con 300 kg durante 100 días (3,3 meses) en dos tandas sucesivas y sale novillito de 400 kg (variante recría larga: entra a corral con 330 kg) | Corral novillo pesado: Entra novillito recriado de 250 kg y sale novillo pesado de 480 kg (+44 días adicionales de encierre respecto al liviano) | Feedlot puro: 2,3 ciclos anuales (~5,2 meses por ciclo)",
        "unidad": "kg/cabeza y días/ciclos",
        "fuente": "SAGyP - Boletín Trimestral N° 59 (Pág. 58-66) y Boletín N° 10 (Pág. 58)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "2. Cría",
        "dato": "Parámetros de cría en Zona Núcleo (Pergamino)",
        "valor": "SIN FUENTE de modelo oficial para Zona Núcleo (SAGyP explicita en Pág. 82 del Boletín N° 59 que no modela cría en la Región Norte de Buenos Aires porque la actividad principal es la agricultura; el stock de Pergamino registra 51.613 vacas, 18.781 terneros y 20.020 terneras = relación ternero+ternera/vaca de 75,2% y 2.114 toros = 4,1 toros/100 vacas)",
        "unidad": "% y cabezas",
        "fuente": "SAGyP Boletín N° 59 (Pág. 82) y UNICEN Anexo MAGyP Stock Pergamino (Pág. 46)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad / Carga animal media anual en Invernada (Alta Producción, Media Producción y Santa Fe Centro)",
        "valor": "Alta Producción (70% praderas, 30% verdeos invierno): 2,71 EV/ha (2,80 cab/ha; 847 kg PV/ha; 605 kg carne/ha/año) | Media Producción (80% praderas, 20% verdeos invierno): 1,44 EV/ha (1,64 cab/ha; 492 kg PV/ha; 260 kg carne/ha/año) | Santa Fe Centro (80% praderas, 20% campo natural): 0,51 EV/ha (0,60 cab/ha; 75 kg carne/ha/año)",
        "unidad": "EV/ha y cab/ha",
        "fuente": "SAGyP - Boletín Trimestral N° 10 Resultados Económicos Ganaderos (Pág. 33-35)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000019-2014/120609_Bolet%C3%ADn%20N%C2%B0%2010%20-%20JUNIO%202014.pdf",
        "fecha": "2014-05"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Producción de forraje de pasturas de festuca alta + leguminosas en INTA EEA Pergamino",
        "valor": "Promedio anual en Pergamino: 5.400 kg MS/ha/año (rango según precipitaciones: 3.500 a 7.200 kg MS/ha/año; hasta 12.000 kg MS/ha/año con fertilización) | Tasa de acumulación neta diaria en Pergamino: 47,3 kg MS/ha/día en primavera húmeda (15/08 al 15/12/2020) y 15,6 kg MS/ha/día en otoño (15/03 al 15/06) y primavera seca | Eficiencia de pastoreo a ras del suelo: 35,9% (otoño) a 62,8% (primavera), y 50% en mezclas base alfalfa",
        "unidad": "kg MS/ha/año y kg MS/ha/día",
        "fuente": "UNNOBA / INTA EEA Pergamino - Eficiencia de pastoreo y acumulación neta de forraje en Festuca arundinacea en Pergamino (Pág. 1, 10, 16-19)",
        "link": "https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y",
        "fecha": "2020 / 2021 (dato más viejo)"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Consumo diario de un Equivalente Vaca (EV)",
        "valor": "18,54 Mcal EM/día = 8,003 a 11,384 kg MS/día según digestibilidad (70% a 50%)",
        "unidad": "kg MS/EV/día",
        "fuente": "UBA FCV / INTA Balcarce (Pág. 5 y 14)",
        "link": "http://dpd.fvet.uba.ar/cartelera/00030355.pdf",
        "fecha": "2020 (dato más viejo)"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Engorde a corral y Recría+Corral - Días de encierre, ganancia diaria, servicio de hotelería y precio de maíz (2026)",
        "valor": "Días de encierre en terminación de recría: 100 días (de 300 a 400 kg => ADPV = 1,00 kg/día) | Ciclos anuales de feedlot puro: 2,3 ciclos/año (umbral de indiferencia: 1,75 ciclos/año) | Tarifa servicio de hotelería de feedlot (febrero 2026): 430 ARS/cab/día (0,28 USD/cab/día al TC BNA 1.560 ARS/USD) | Precio grano de maíz (agosto 2026): 178 USD/t = 0,178 USD/kg (277,68 ARS/kg) | Relación maíz/novillo (agosto 2026): 56 kg de novillo por tonelada de maíz (promedio histórico: 102 kg/t) | Conversión alimenticia exacta del cuadro de feedlot (en imagen en PDF 2026): SIN FUENTE",
        "unidad": "días, kg/día, ARS/cab/día, USD/kg",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 58-66, 74, 76)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Composición del precio neto del novillo e incidencia de costos en Invernada de Alta Producción (agosto 2026)",
        "valor": "Compra de ternero (CT): 73% (vs. 69% en ago-2025) | Costos directos, estructura y amortizaciones (C): 21% (vs. 25% en ago-2025) | Resultado Neto (RN): 6% (vs. 6% en ago-2025) | En Invernada Santa Fe: 67% compra ternero, 25% costos, 8% resultado neto",
        "unidad": "% del precio neto del novillo",
        "fuente": "SAGyP - Boletín Trimestral N° 59 Resultados Económicos Ganaderos (Pág. 43)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-08"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Margen bruto de Invernada de Alta Producción (actualizado a 2026) y estructura porcentual de costos",
        "valor": "Margen Bruto (2026): 432.552 ARS/ha (277,28 USD/ha al TC BNA 1.560 ARS/USD) | Estructura porcentual del costo total (sin compra de ternero, Boletín N° 10 Pág. 34): Alimentación 68%, Estructura e impuestos 17%, Personal 10%, Sanidad 3%, Amortizaciones 2% | Gastos comercialización: 6,5% en compra de ternero y 7,0% en venta de novillo | Mortandad en invernada: 2% | Desbaste: 5%",
        "unidad": "ARS/ha, USD/ha y %",
        "fuente": "SAGyP - Boletín Trimestral N° 59 (Pág. 67) y Boletín N° 10 (Pág. 34)",
        "link": "https://www.magyp.gob.ar/sitio/areas/bovinos/modelos/resultados/_archivos//000001_Bolet%C3%ADn%20trimestral/000007-2026/000002-Bolet%C3%ADn%20N%C2%BA%2059%20septiembre%20%202026.pdf",
        "fecha": "2026-09"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Precios Rosgan (Bolsa de Comercio de Rosario, referencia Zona Núcleo) y MAG Cañuelas - Septiembre 2026",
        "valor": "Rosgan (Sep-2026): Terneros 6.135,40 ARS/kg (3,93 USD/kg), Terneras 5.813,33 ARS/kg (3,73 USD/kg), Novillos 1-2 años 5.329,43 ARS/kg (3,42 USD/kg), Novillos 2-3 años 4.551,10 ARS/kg (2,92 USD/kg), Terneros Holando 4.956,45 ARS/kg (3,18 USD/kg), Vaquillonas invernada 5.094,98 ARS/kg (3,27 USD/kg), Vacas invernada 3.221,24 ARS/kg (2,06 USD/kg) | SAGyP/MAG (Sep-2026): Liviano consumo hasta 390 kg 4.613 ARS/kg (2,96 USD/kg), Novillo +430 kg 4.275 ARS/kg (2,74 USD/kg) (TC BNA 1.560 ARS/USD) | Ventaja promedio novillo pesado vs. novillito liviano en 2026: +0,72% con picos mensuales >12%",
        "unidad": "ARS/kg vivo y USD/kg vivo",
        "fuente": "Rosgan Septiembre 2026, SAGyP Tablero Septiembre 2026 y Boletín N° 59 (Pág. 69)",
        "link": "https://rosgan.com.ar/indices",
        "fecha": "2026-09"
      },
      {
        "tema": "7. Capital",
        "dato": "Valor de reposición del ternero de invernada (180 kg) y tiempos de inmovilización del capital",
        "valor": "Ternero de 180 kg (a 6.135,40 ARS/kg Rosgan Sep-2026): 1.104.372 ARS/cabeza (707,93 USD/cab al TC BNA 1.560 ARS/USD) | Inmovilización: 11,5 meses en Invernada de Alta Producción, 15,8 meses en Invernada de Media Producción, 22,2 meses en Invernada Santa Fe Centro, y 100 días (3,3 meses) en la etapa de terminación a corral",
        "unidad": "ARS/cab, USD/cab y meses",
        "fuente": "Rosgan Septiembre 2026 y SAGyP Boletín N° 10 (Pág. 33-35) y Boletín N° 59 (Pág. 62)",
        "link": "https://rosgan.com.ar/indices",
        "fecha": "2026-09"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "Impuestos y retenciones sobre la hacienda y la carne (Argentina)",
        "valor": "Derechos de exportación categoría vaca (cortes A-E): 0% (Decreto 697/2024) | Derechos de exportación resto cortes bovinos: 6,75% | IVA hacienda y carne bovina: 10,5%",
        "unidad": "%",
        "fuente": "Argentina.gob.ar - Decreto 697/2024 y UNLP SEDICI",
        "link": "https://www.argentina.gob.ar/noticias/el-gobierno-elimina-derechos-de-exportacion-en-productos-agroindustriales-para-fortalecer",
        "fecha": "2024-08"
      },
      {
        "tema": "9. Riesgos",
        "dato": "Riesgos climáticos y de mercado en Zona Núcleo / Pampeana y respuesta del productor",
        "valor": "Riesgos: sequía primavero-estival (como la primavera seca y cálida de 2021 en Pergamino que redujo la densidad de macollos de festuca de 1.948 a 559 macollos/m2 con pastoreo severo a 5 cm) y desfasaje de la relación compra/venta (1,46 en 2026) | Respuestas: mantener remanente post-pastoreo de 8 a 11 cm (900-1.150 kg MS verde/ha) para evitar pérdida de macollos por estrés térmico en diciembre-enero; alargar la recría a pasto (+30 kg con verdeo de verano) y acortar los días de encierre a corral para reducir el consumo de maíz y mejorar un 27% el margen de recría",
        "unidad": "estrategia técnica",
        "fuente": "UNNOBA / INTA Pergamino (Pág. 14, 19-20) y SAGyP Boletín N° 59 (Pág. 65-66)",
        "link": "https://repositorio.unnoba.edu.ar/xmlui/bitstream/handle/23601/697/041123_GUILLERMO%20ESTEBAN%20MEDINA%20ING%20AGRON%C3%93MICA.pdf?sequence=3&isAllowed=y",
        "fecha": "2021 / 2026-09"
      }
    ]
  },
  {
    "zona": "4. Mato Grosso (Brasil)",
    "datos": [
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría, Recría y Engorda a pasto en Mato Grosso / Brasil Central - Categorías y pesos de entrada y salida",
        "valor": "Cría: Entra novilha (1° cría a los 2,5 años en ILP o 4 años en pasto degradado), Sale bezerro/a al destete (7 meses) con 160 a 210 kg (7@ = 210 kg en indicador IMEA) | Recría a pasto: Macho entra con 150-210 kg y sale boi magro con 350-360 kg (12@); Hembra entra con 140-180 kg y sale con 270-305 kg | Engorda a pasto: Macho entra con 350-360 kg y sale boi gordo con 480 kg (edad de faena: 2,5 años en ILP a 4 años en sistema extensivo); Hembra entra con 270 kg y sale con 400 kg",
        "unidad": "kg/cabeza y meses/años",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 7, 16, 26, 28, 30) e IMEA Boletim N° 911 (Pág. 2-3)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Semiconfinamento y Confinamento (corral) - Categorías, pesos, duración y meses de entrega",
        "valor": "Semiconfinamento (en época seca): Macho entra con 400 kg y sale con 460 kg en 60 días (ADPV 1,0 kg/día; o 80 días entrando con 360 kg en pasto diferido de 8 t MS/ha); Novilha/vaca entra con 320 kg y gana 50-70 kg | Confinamento: 1) Novilhos castrados (18-30 meses): entran con 350-420 kg, salen con 480-520 kg en 70 a 100 días; 2) Machos inteiros/tourinhos (18-30 meses): entran con 370-440 kg, salen con 500-550 kg en 90 a 120 días; 3) Novilhas (20-30 meses): entran con 280-320 kg, salen con 360-420 kg en 60 a 90 días; 4) Vacas de descarte (>3 años): entran con 340-420 kg, salen con 400-460 kg en 50 a 70 días | Ventana de venta del confinamento en MT: 48,31% se entrega entre septiembre y noviembre (entressafra)",
        "unidad": "kg/cabeza y días",
        "fuente": "Embrapa Gado de Corte - Nutrição de Bovinos de Corte Cap. 9 (Pág. 127, 132) e IMEA Boletim N° 910 (Pág. 2)",
        "link": "https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf",
        "fecha": "2015 (dato más viejo) / 2026-08"
      },
      {
        "tema": "2. Cría",
        "dato": "% de natalidad, % de destete y % de mortalidad (Pastura degradada vs. Pastura recuperada con ILP)",
        "valor": "Pastura degradada: Natalidad 60%, Mortalidad hasta destete 8%, Destete 54%, Mortalidad post-destete 4% | Pastura recuperada con ILP: Natalidad 82%, Mortalidad hasta destete 3%, Destete 78%, Mortalidad post-destete 1%",
        "unidad": "%",
        "fuente": "Embrapa Gado de Corte - DOC 182 Diagnóstico para o planejamento da propriedade (Pág. 7, Tabela 1)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "2. Cría",
        "dato": "% de reposición anual de vientres, edad de descarte y relación toro:vaca en Mato Grosso",
        "valor": "SIN FUENTE de valor único fijo en las tablas abiertas de IMEA/Embrapa (el protocolo de diagnóstico DOC 182 releva la relación touro:vaca y el % de descarte anual en cada propiedad; la tasa de desfrute total del rodeo pasa de 17% en pasto degradado a 30-35% en ILP)",
        "unidad": "%",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 7, 10, 24)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad / Lotación por nivel tecnológico y en período seco (UA/ha y animales/ha, donde 1 UA = 450 kg PV)",
        "valor": "Pasto degradado: 0,7 a 0,9 anim/ha (30 a 45 kg carne/ha/año) | Pasto mejorado: 1,5 anim/ha (60 kg/ha/año) | Pasto intensivo: 2,0 anim/ha (90 kg/ha/año) | Intensivo + suplemento: 2,2 anim/ha (120 kg/ha/año) | + Confinamento: 2,5 anim/ha (150 kg/ha/año) | + Integración ILP: 3,0 anim/ha (230 a 330 kg/ha/año) | Recría-engorda intensiva: 5,0 anim/ha (450 kg/ha/año) | En período seco (mayo-septiembre) con suplementación estratégica: 1,0 UA/ha (y 1,0 a 2,0 UA/ha en semiconfinamento)",
        "unidad": "animales/ha y UA/ha",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 7, 10, Tabelas 1 y 3) y Cap. 9 (Pág. 123, 126)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Masa de forraje acumulada (vedação / diferimiento) para la estación seca en Brasil Central",
        "valor": "4.000 a 6.000 kg MS/ha al inicio de la seca (diferimiento de 1/3 del área en febrero para uso en junio-julio y 2/3 en marzo para uso en agosto-septiembre) | Hasta 8.000 kg MS/ha con diferimiento prolongado y fertilización nitrogenada | Producción en kg MS/ha desagregada por las 4 estaciones para campo natural y pasturas en MT: SIN FUENTE",
        "unidad": "kg MS/ha",
        "fuente": "Embrapa Gado de Corte - Nutrição de Bovinos de Corte Cap. 9 (Pág. 122, 126-127)",
        "link": "https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf",
        "fecha": "2015 (dato más viejo)"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Equivalencias en Unidad Animal (UA = 450 kg PV) y consumo diario",
        "valor": "Vaca preñada/lactante: 1,20 UA | Vaca vacía: 1,00 UA | Novilla 2-3 años (305 kg): 0,75 UA | Novilla 1-2 años (230 kg): 0,60 UA | Bezerro/a (150 kg): 0,44 UA | Macho 1-2 años (255 kg): 0,65 UA | Macho 2-3 años (360 kg): 0,85 UA | Macho 3-4 años (450 kg): 1,00 UA | Toro (>600 kg): 1,50 UA | Oferta en confinamiento: 10 kg/cab/día en adaptación hasta 18 kg/cab/día en dieta final (75% concentrado : 25% voluminoso en base seca)",
        "unidad": "UA/cabeza y kg/día",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 15-16, Tabela 8) y Cap. 9 (Pág. 134, Quadros 9.5 y 9.6)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Ganancia diaria de peso (GMD) según cultivar forrajero y nivel de suplementación",
        "valor": "En pasturas perennes (g/día): B. humidicola 400, B. decumbens 480, B. brizantha cv. Xaraés 480, cv. Marandu 500, cv. Piatã 530, Andropogon 550, Panicum cv. Massai 600, cv. Tanzânia 650, cv. Mombaça 650, Tifton 750 | Anuales: Sorgo forrajero 900, Milheto 950, Avena/Azevém 1.000 | En época seca: Sal mineral con 30% urea (consumo ~100 g/UA/día) = mantenimiento de peso; Sal proteinado (consumo 1 a 3 g/kg PV/día) = 0,20 a 0,40 kg/día; Semiconfinamento (concentrado al 0,7% a 2,0% del PV durante 60-80 días) = ~1,00 kg/día | En confinamento (70-120 días): ~1,30 a 1,50 kg/día | Conversión alimenticia exacta de confinamento en MT en 2026: SIN FUENTE",
        "unidad": "g/día y kg/día",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 9, Tabela 2) y Cap. 9 (Pág. 123-127, 132)",
        "link": "https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Costo de la diária confinada en Mato Grosso (Julio 2026)",
        "valor": "13,62 BRL/cabeza/día (+3,57% interanual vs. 2025), equivalente a 2,53 USD/cabeza/día al PTAX venta del BCB de 5,3744 BRL/USD del 29/10/2026 (con oferta final de 18 kg de ración/día equivale a ~0,76 BRL/kg o 0,14 USD/kg)",
        "unidad": "BRL/cab/día y USD/cab/día",
        "fuente": "IMEA - Boletim Semanal Bovinocultura de Corte N° 910 (Pág. 2) y BCB PTAX",
        "link": "https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/910",
        "fecha": "2026-07"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Costo Operacional Total (COT) por actividad en Mato Grosso (serie trimestral 2025-2026 de IMEA)",
        "valor": "Cría: 281,82 (2T/25), 279,64 (3T/25), 287,62 (4T/25), 290,71 (1T/26), 295,79 BRL/@ en 2T/26 (= 55,04 USD/@) | Recría/Engorda: 324,89 (2T/25), 325,71 (3T/25), 334,94 (4T/25), 351,63 (1T/26), 369,55 BRL/@ en 2T/26 (= 68,76 USD/@) | Ciclo Completo: 169,10 (2T/25), 172,94 (3T/25), 177,76 (4T/25), 178,01 (1T/26), 182,25 BRL/@ en 2T/26 (= 33,91 USD/@) [TC BCB PTAX 29/10/2026 = 5,3744 BRL/USD] | Desagregado en R$/cab de sanidad, mano de obra y estructura en 2026: SIN FUENTE en el boletín semanal abierto",
        "unidad": "BRL/@ y USD/@",
        "fuente": "IMEA - Boletim Semanal Bovinocultura de Corte N° 911 (Pág. 3) y BCB PTAX",
        "link": "https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911",
        "fecha": "2026-06"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Calendario sanitario de referencia (Embrapa Gado de Corte)",
        "valor": "Fiebre aftosa (según estatus sanitario estadal/MAPA), Brucelosis en bezerras, Clostridiosis en bezerros a los 4 y 7 meses de edad, vacuna contra diarrea neonatal en hembras gestantes (4 meses antes del parto), botulismo (anual), rabia (zonas endémicas), vermifugación (novilhas del destete a los 2 años y vacas en periparto) y control de ectoparásitos (mosca de los cuernos, garrapata y berne)",
        "unidad": "calendario técnico",
        "fuente": "Embrapa Gado de Corte - DOC 182 (Pág. 25, 29, 31)",
        "link": "https://www.infoteca.cnptia.embrapa.br/bitstream/doc/897507/1/DOC182.pdf",
        "fecha": "2011-06"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Precios en Mato Grosso por categoría (IMEA Agosto 2026 y comparativo Ago-2025 / Jul-2026)",
        "valor": "Boi gordo a prazo (MT, 17-21/08/2026): 325,88 a 329,86 BRL/@ (60,64 a 61,38 USD/@) [media 3 semanas ago/26: 328,33 BRL/@ = 61,09 USD/@] | Vaca gorda a prazo (MT, 17-21/08/2026): 306,11 a 308,59 BRL/@ (56,96 a 57,42 USD/@) | Bezerro 7@ (210 kg, MT): 3.093,06 BRL/cab (20-24/07/26) a 3.322,83 BRL/cab (17-21/08/26; 15,82 BRL/kg = 618,27 USD/cab o 2,94 USD/kg) | Boi magro 12@ (360 kg, MT): 13,16 BRL/kg = 4.737,60 BRL/cab (2,45 USD/kg = 881,51 USD/cab) | Bezerra de ano 6@ (180 kg, MT): 10,14 BRL/kg (ago/25), 12,45 BRL/kg (jul/26), 12,80 BRL/kg (ago/26 = 2,38 USD/kg) | Novilha 8,5@ (255 kg, MT): 9,68 BRL/kg (ago/25), 11,21 BRL/kg (jul/26), 11,71 BRL/kg (ago/26 = 2,18 USD/kg) | Vaca solteira (MT): 9,23 BRL/kg (ago/25), 10,50 BRL/kg (jul/26), 10,94 a 11,06 BRL/kg (ago/26 = 2,04 a 2,06 USD/kg) [TC BCB PTAX 29/10/2026 = 5,3744 BRL/USD]",
        "unidad": "BRL/@, BRL/kg, BRL/cab y USD",
        "fuente": "IMEA - Boletim Semanal Bovinocultura de Corte N° 911 (Pág. 2-3) y N° 910 (Pág. 2-3)",
        "link": "https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911",
        "fecha": "2026-08"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Evolución de precios CEPEA (2025 vs. Septiembre y Octubre 2026) y estacionalidad",
        "valor": "Boi gordo CEPEA: 319,2 BRL/@ (fin de 2025) -> 364,3 BRL/@ (sep-2026) -> 389,9 BRL/@ al 30/10/2026 (+22,1% en 2026; 72,55 USD/@) | Bezerro CEPEA (MS): 3.066,6 BRL/cab (fin de 2025; 434,4 BRL/@) -> 3.446,1 BRL/cab (sep-2026; 517,7 BRL/@) -> 3.573,0 BRL/cab al 30/10/2026 (+16,5% en 2026; 534,7 BRL/@; 664,82 USD/cab al PTAX de 5,3744 BRL/USD) | Estacionalidad: mayores precios en la entressafra (periodo seco, especialmente septiembre-noviembre, con futuros B3 nov/26 en 406,90 BRL/@) | Serie completa de los 24 meses mes a mes para todas las categorías en MT: SIN FUENTE en boletines abiertos",
        "unidad": "BRL/@, BRL/cab y USD",
        "fuente": "Farmnews / CEPEA - Preço do boi gordo e bezerro: destaques de outubro de 2026",
        "link": "https://www.farmnews.com.br/mercado/preco-do-boi-gordo-e-bezerro-destaques-de-outubro-de-2026/",
        "fecha": "2026-10"
      },
      {
        "tema": "7. Capital",
        "dato": "Valor de un ternero (bezerro 210 kg), boi magro (360 kg) y vaca solteira, y relación de troca en MT (Agosto 2026)",
        "valor": "Bezerro 210 kg (7@): 3.322,83 BRL/cab (618,27 USD/cab) | Boi magro 360 kg (12@ a 13,16 BRL/kg): 4.737,60 BRL/cab (881,51 USD/cab) | Vaca solteira (ej. 390 kg a 11,06 BRL/kg): 4.313,40 BRL/cab (802,58 USD/cab) | Relación de troca boi gordo (21@) / bezerro (210 kg): 2,07 a 2,15 bezerros por boi gordo en jul-ago 2026 (vs. 2,29 en ago-2025) | Tiempo de inmovilización: 70 a 120 días en confinamento, 60 a 80 días en semiconfinamento, 12 a 24 meses en recría-engorda a pasto",
        "unidad": "BRL/cab, USD/cab y cab/cab",
        "fuente": "IMEA - Boletim N° 911 (Pág. 2-3) y N° 910 (Pág. 2)",
        "link": "https://publicacoes.imea.com.br/relatorio-de-mercado/bs-bovinoculturadecorte/911",
        "fecha": "2026-08"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "FETHAB Gado y FETHAB Carne en Mato Grosso (vigencia prorrogada hasta diciembre 2026 por Lei Estadual N° 13.357 del 13/05/2026)",
        "valor": "UPF/MT base (Enero 2025 mantenida para 2026 por Lei 13.002/2025 y Lei 13.357/2026): 243,49 BRL (45,31 USD) | FETHAB Gado en pie para faena o salida interestatal/exportación: 11,5% UPF/MT (FETHAB básico) + 11,5% UPF/MT (FETHAB adicional hasta 31/12/2026) + 1,26% UPF/MT (entidad de la cadena INPECMT/IMAmt) = 24,26% de la UPF/MT por cabeza = 59,07 BRL/cabeza (10,99 USD/cab al PTAX de 5,3744 BRL/USD), con reducción porcentual para hembras enviadas a faena según Lei 13.032/2025 y Decreto 1.940/2026 | FETHAB Carne en exportación: 0,03% de la UPF/MT por kg (= 0,073 BRL/kg)",
        "unidad": "% de UPF/MT, BRL/cab y USD/cab",
        "fuente": "Sygma Sistemas / SEFAZ-MT - Guia Cálculo FETHAB MT 2026 y SEFAZ-MT Decreto 1.940/2026",
        "link": "https://www.sygmasistemas.com.br/guia-calculo-fethab-mato-grosso/",
        "fecha": "2026-01"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "FUNRURAL y SENAR sobre comercialización de bovinos en Brasil (Lei 13.606/2018)",
        "valor": "Produtor Rural Pessoa Física (modalidad comercialización): 1,5% sobre el valor bruto de venta (1,2% INSS + 0,1% RAT + 0,2% SENAR) | Produtor Rural Pessoa Jurídica (modalidad comercialización): 2,05% (1,7% INSS + 0,1% RAT + 0,25% SENAR) | Exención: venta de ganado destinado a reproducción o cría/recría directamente entre productores rurais está exenta de INSS/RAT, pagando únicamente 0,2% (PF) o 0,25% (PJ) de SENAR",
        "unidad": "% sobre facturación bruta",
        "fuente": "Sygma Sistemas / Receita Federal - Funrural cálculo e alíquotas (Lei 13.606/2018)",
        "link": "https://www.sygmasistemas.com.br/funrural-calculo-e-aliquotas/",
        "fecha": "2025-01"
      },
      {
        "tema": "9. Riesgos",
        "dato": "Riesgo de estación seca (mayo a septiembre) y degradación de pasturas, y estrategias del productor en MT",
        "valor": "Riesgos: caída abrupta de crecimiento y lignificación de pasturas tropicales entre mayo y septiembre (seca) y degradación de pasturas (que reduce la productividad de 300 a 30 kg carne/ha/año) | Respuestas técnicas: 1) Vedação/diferimiento escalonado de pasturas (1/3 en febrero y 2/3 en marzo para acumular 4 a 6 t MS/ha) con lotación de ~1 UA/ha; 2) Suplementación en seca con sal mineral con 30% urea (100 g/UA/día para mantenimiento) o sal proteinado (1-3 g/kg PV/día para ganar 200-400 g/día); 3) Semiconfinamento por 60-80 días o confinamento (aliviando pasturas en la seca y vendiendo el 48,31% entre septiembre y noviembre); 4) Renovación de pasturas mediante Integración Lavoura-Pecuária (ILP)",
        "unidad": "estrategia técnica",
        "fuente": "Embrapa Gado de Corte - Cap. 9 (Pág. 121-129), DOC 182 (Pág. 6-10) e IMEA Boletim N° 910 (Pág. 2)",
        "link": "https://www.alice.cnptia.embrapa.br/alice/bitstream/doc/1011236/1/NutricaoAnimalCAPITULO09.pdf",
        "fecha": "2015 / 2026-08"
      }
    ]
  },
  {
    "zona": "5. Iowa / Midwest (Estados Unidos)",
    "datos": [
      {
        "tema": "1. Actividades habituales",
        "dato": "Cría (Beef Cow-Calf, Calves Sold) - Categorías, pesos de salida y calendario",
        "valor": "Entra: Vaquillona de reposición (0,20 cab/unidad vaca) y Toro ($5.000/cab, 0,04 toros/vaca) | Sale: Ternero macho destetado de 550 lb (249,5 kg; 0,46 cab vendidas/vaca), Ternera destetada de 500 lb (226,8 kg; 0,26 cab vendidas/vaca) y Vaca de descarte (cull cow) de 1.350 lb (612,3 kg; 0,18 cab vendidas/vaca) | Duración ciclo anual: 12 meses (parición primavera mar-abr, destete y venta otoño oct-nov)",
        "unidad": "lb/cabeza, kg/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21: 2026 Livestock Enterprise Budgets for Iowa (Pág. 15-16)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Recría de invierno a corral (Backgrounding Steer Calves, Winter Corn & Hay Ration) - Pesos y duración",
        "valor": "Entra: Ternero (steer calf) de 450 lb (204,1 kg) en otoño (oct-nov) | Sale: Novillito feeder de 750 lb (340,2 kg) en primavera (mar-abr) | Duración: 5 meses (150 días; ganancia total 300 lb = 136,1 kg)",
        "unidad": "lb/cabeza, kg/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 14)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Recría de verano a pasto (Backgrounding Steer Calves, Summer Improved Pasture) - Pesos y duración",
        "valor": "Entra: Ternero (steer calf) de 525 lb (238,1 kg) en primavera (mayo) | Sale: Novillito feeder de 750 lb (340,2 kg) en otoño (septiembre-octubre) | Duración: 5 meses (150 días; ganancia total 225 lb = 102,1 kg)",
        "unidad": "lb/cabeza, kg/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 14)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Engorde a corral de novillitos de año (Finishing Yearling Steers) - Pesos y duración",
        "valor": "Entra: Yearling feeder steer de 750 lb (340,2 kg) | Sale: Fed steer terminado de 1.350 lb (612,3 kg) | Duración: 6,5 meses (195 días; ganancia total 600 lb = 272,2 kg)",
        "unidad": "lb/cabeza, kg/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 11)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "1. Actividades habituales",
        "dato": "Engorde a corral de terneros (Finishing Steer Calves) y de vaquillonas de año (Finishing Yearling Heifers) - Pesos y duración",
        "valor": "Steer Calves: Entra ternero de 550 lb (249,5 kg), Sale novillo terminado de 1.350 lb (612,3 kg), Duración 9 meses (270 días; ganancia 800 lb = 362,9 kg) | Yearling Heifers: Entra vaquillona de 700 lb (317,5 kg), Sale vaquillona terminada de 1.350 lb (612,3 kg), Duración 270 días / 9 meses (ganancia 650 lb = 294,8 kg)",
        "unidad": "lb/cabeza, kg/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 12-13)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "2. Cría",
        "dato": "% de preñez, % de destete, % de mortandad, % de reposición, descarte y toros cada 100 vacas en Iowa",
        "valor": "% de preñez: SIN FUENTE en B1-21 (se reporta directamente destete) | % de destete (calf crop weaned): 92% de las vacas del rodeo (0,90 terneros comercializados/retenidos por vaca tras mortandad) | % de reposición anual de vientres: 20% (0,20 bred heifer por vaca) | % de mortandad anual de vacas y vaquillonas de reposición: 2% | Tasa de venta anual de vacas de descarte (cull cows): 18% (0,18 cab/vaca/año; vida útil productiva implícita ~5 pariciones, vida útil de toros = 3 años) | Toros cada 100 vacas: 4,0 (1 toro cada 25 vacas = 0,04 bull/cow unit)",
        "unidad": "% y toros/100 vacas",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 15-16)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Receptividad (AUM/acre y EV/ha) y producción anual de forraje por tipo de pastura y rastrojo en Iowa",
        "valor": "Bluegrass sin mejorar: 1,0-1,5 ton/acre (2.242-3.363 kg/ha) y 3,0 AUM/acre (7,41 AUM/ha) | Bluegrass mejorado con leguminosa o N: 1,5-2,5 ton/acre (3.363-5.604 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) | Lotus (birdsfoot trefoil) + gramínea: 3,0-4,0 ton/acre (6.725-8.967 kg/ha) y 5,0 AUM/acre (12,36 AUM/ha) | Pasto ovillo o bromegrass puro: 3,0-4,0 ton/acre (6.725-8.967 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) | Pasto ovillo o bromegrass + leguminosa o N: 4,0-5,0 ton/acre (8.967-11.209 kg/ha) y 6,5 AUM/acre (16,06 AUM/ha) | Gramíneas estivales (warm season): 4,0-5,0 ton/acre (8.967-11.209 kg/ha) y 4,0 AUM/acre (9,88 AUM/ha) | Alfalfa + gramínea: 4,0-6,0 ton/acre (8.967-13.450 kg/ha) y 6,0 AUM/acre (14,83 AUM/ha) | Rastrojo de maíz (cornstalks): 0,5-1,0 ton/acre (1.121-2.242 kg/ha; 3.467 lb MO/acre en ASL-1636) y 0,7 AUM/acre (1,73 AUM/ha) | El pastoreo rotativo incrementa la producción ~25% | Desagregado trimestral por estación en kg MS/ha: SIN FUENTE en C2-23 (en invierno no hay crecimiento por nieve/congelamiento)",
        "unidad": "short tons/acre, kg/ha y AUM/acre (y AUM/ha)",
        "fuente": "Iowa State University Extension - Ag Decision Maker File C2-23: Computing a Pasture Rental Rate (Pág. 2, Table 1, Ago 2025) y ASL-1636",
        "link": "https://www.extension.iastate.edu/agdm/wholefarm/pdf/c2-23.pdf",
        "fecha": "2025-08"
      },
      {
        "tema": "3. Pasto y carga",
        "dato": "Superficie asignada por cabeza en los presupuestos 2026 de Iowa y consumo diario por Animal Unit (AU)",
        "valor": "Cría (Beef Cow-Calf): 2,5 acres (1,01 ha) de pastura permanente ($63/acre) + 4,0 acres (1,62 ha) de rastrojo de maíz ($13/acre) + 2,1 short tons (1.905 kg) de heno alfalfa-brome + 4 bushels (101,6 kg) de maíz por unidad vaca/año | Recría de verano (Summer Backgrounding): 0,7 acres (0,28 ha) de pastura mejorada ($102/acre) por novillito durante 5 meses | Consumo de 1 Animal Unit (AU, vaca de 1.000 lb con ternero): 26 lb/día de forraje seco a estufa (11,79 kg MS/día, 100% MS) o 30 lb/día de forraje secado al aire (13,61 kg/día al 87% MS) | Equivalencias AU (Table 2 C2-23): Vaca adulta 1,0-1,4 AU; Toro 1,5 AU; Novillito/vaquillona de año 0,7-0,9 AU; Vaquillona 2 años 1,0-1,2 AU; Ternero 0,4 AU",
        "unidad": "acres/cab, ha/cab y kg MS/AU/día",
        "fuente": "ISU Extension File B1-21 (Pág. 14-15), File C2-23 (Pág. 2) y NDSU / NRCS Range and Pasture Handbook",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Finishing Yearling Steers (750 a 1.350 lb en 195 días) - ADPV, dieta, conversión y costo de ración (2026)",
        "valor": "Ganancia total: 600 lb (272,2 kg) en 195 días => ADPV = 3,08 lb/día (1,40 kg/día) | Dieta Maíz + Heno: 60 bu maíz (3.360 lb = 1.524,1 kg a $4,12/bu = $247,20) + 1,14 tons MDGS (2.280 lb = 1.034,2 kg a $100/ton = $114,00) + 0,30 tons heno (600 lb = 272,2 kg a $81/ton = $24,30) + 95 lb suplemento/mineral (43,1 kg a $0,23/lb = $21,85) -> Total alimento tal cual: 6.335 lb (2.873,5 kg), Conversión tal cual: 10,56 kg alimento/kg ganancia (conversión en base seca ~7,9 kg MS/kg ganancia considerándose ~50% MS en MDGS), Costo total alimentación: $407,35 USD/cab ($0,1418 USD/kg tal cual; $0,679 USD/lb de ganancia = $1,50 USD/kg ganado) | Dieta Maíz + Silaje: 49,25 bu maíz ($202,91) + 1,14 tons MDGS ($114,00) + 1,32 tons silaje de maíz ($65,21 a $49,40/ton) + 95 lb suplemento ($21,85) -> Costo total alimentación: $403,97 USD/cab",
        "unidad": "kg/día, kg/kg y USD",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 2, 3, 11)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Finishing Steer Calves (550 a 1.350 lb en 270 días) - ADPV, dieta, conversión y costo de ración (2026)",
        "valor": "Ganancia total: 800 lb (362,9 kg) en 270 días => ADPV = 2,96 lb/día (1,34 kg/día) | Dieta Maíz + Heno: 69 bu maíz (3.864 lb = 1.752,7 kg; $284,28) + 1,40 tons MDGS (2.800 lb = 1.270,1 kg; $140,00) + 0,53 tons heno (1.060 lb = 480,8 kg; $42,93) + 135 lb suplemento (61,2 kg; $31,05) -> Total alimento tal cual: 7.859 lb (3.564,8 kg), Conversión tal cual: 9,82 kg/kg (en base seca ~7,5 kg MS/kg), Costo alimentación: $498,26 USD/cab ($0,1398 USD/kg tal cual; $1,37 USD/kg ganado) | Dieta Maíz + Silaje: 50 bu maíz ($206,00) + 1,40 tons MDGS ($140,00) + 2,26 tons silaje de maíz ($111,64) + 135 lb suplemento ($31,05) -> Costo alimentación: $488,69 USD/cab",
        "unidad": "kg/día, kg/kg y USD",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 12)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "4. Suplementación y corral",
        "dato": "Finishing Yearling Heifers (700 a 1.350 lb en 270 días) y Backgrounding Steer Calves (150 días) - ADPV y costos de alimentación (2026)",
        "valor": "Yearling Heifers (ganan 650 lb = 294,8 kg en 270 días => ADPV = 2,41 lb/día = 1,09 kg/día): Dieta Maíz+Heno (80 bu maíz $329,60 + 1,5 tons MDGS $150,00 + 0,40 tons heno $32,40 + 160 lb supl. $36,80) = $548,80 USD/cab (8.440 lb tal cual = 3.828,3 kg; conversión tal cual 12,98 kg/kg; Dieta Maíz+Silaje = $552,58 USD/cab) | Winter Backgrounding (450 a 750 lb en 150 días => ADPV = 2,00 lb/día = 0,91 kg/día): 27 bu maíz ($111,24) + 0,5 tons heno alfalfa-brome ($40,50) + 80 lb supl. ($18,40) = $170,14 USD/cab (2.592 lb tal cual = 1.175,7 kg; conversión tal cual 8,64 kg/kg; $0,1447 USD/kg ración) | Summer Backgrounding a pasto (525 a 750 lb en 150 días => ADPV = 1,50 lb/día = 0,68 kg/día): 0,7 acres pastura ($71,40) + fertilización ($14,00) + 35 lb supl. ($8,05) = $93,45 USD/cab | Referencia Iowa Beef Center (novillos Holstein hasta 1.000 lb): ADPV ~3,0 lb/día (1,36 kg/día), consumo 18-20 lb MS/día (8,2-9,1 kg MS/día), conversión 6,0 a 7,0 kg MS/kg ganancia",
        "unidad": "kg/día, kg/kg y USD/cab",
        "fuente": "ISU Extension File B1-21 (Pág. 13-14) e Iowa Beef Center (Feeding Holstein Steers, Pág. 1)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Costos detallados por cabeza en Cría (Beef Cow-Calf, 1 unidad vaca) en Iowa (2026)",
        "valor": "Alimentación total: $451,48 USD/vaca (Pastura 2,5 ac $157,50 + Fertilización pastura $50,00 + Rastrojos 4 ac $52,00 + Heno 2,1 t $170,10 + Maíz 4 bu $16,48 + Sal y minerales 60 lb $5,40) | Veterinaria y sanidad: $25,00 USD/vaca | Maquinaria, combustible y reparaciones: $24,00 USD/vaca | Comercialización y varios: $20,00 USD/vaca | Interés sobre capital operativo (7,11% anual por 6 meses): $18,50 USD/vaca | Mano de obra (8 horas a $20,00/h): $160,00 USD/vaca | Total Costos Variables: $698,98 USD/vaca | Costos Fijos: Maquinaria, equipos y alambrados $105,00 USD/vaca ($41,62 USD/ha sobre 2,5 acres) + Interés/seguro sobre rodeo al 10% $296,00 USD/vaca + Depreciación/reposición de toro $48,00 USD/vaca = Total Costos Fijos $449,00 USD/vaca | COSTO TOTAL ANUAL: $1.147,98 USD/unidad vaca",
        "unidad": "USD/vaca/año (moneda local = USD)",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 15-16)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "5. Costos por cabeza y estructura",
        "dato": "Costos detallados por cabeza en Recría (Backgrounding) y Feedlot (Finishing) en Iowa (2026)",
        "valor": "1) Finishing Yearling Steers (Maíz+Heno): Compra novillito (750 lb a $3,74/lb) $2.805,00 + Interés hacienda (6,5 m al 7,11%) $108,03 + Alimentación $407,35 + Sanidad $8,00 + Maquinaria $11,20 + Comercialización/transporte $16,00 + Interés var. $8,52 + Mano de obra (2,5 h a $20/h) $50,00 + Mortandad (1% compra + 0,5% var.) $31,64 + Costos Fijos instalaciones $22,40 = Costo Total $3.468,14 USD/cab | 2) Finishing Steer Calves (Maíz+Heno): Compra ternero (550 lb a $4,92/lb) $2.706,00 + Interés hacienda (9 m) $144,30 + Alimentación $498,26 + Sanidad $10,00 + Maquinaria $17,60 + Comercialización $14,00 + Interés var. $14,39 + Mano de obra (4 h) $80,00 + Mortandad (2% compra + 1% var.) $63,35 + Costos Fijos $33,60 = Costo Total $3.581,50 USD/cab | 3) Finishing Yearling Heifers (Maíz+Heno): Compra (700 lb a $3,74/lb) $2.618,00 + Interés (270 d) $137,69 + Alimentación $548,80 + Sanidad $8,00 + Maquinaria $11,20 + Comercialización $16,00 + Interés var. $15,57 + Mano de obra (2 h) $40,00 + Mortandad $30,75 + Costos Fijos $25,60 = Costo Total $3.451,62 USD/cab | 4) Backgrounding Invierno: Compra (450 lb a $4,92/lb) $2.214,00 + Interés (5 m) $65,59 + Alimentación $170,14 + Sanidad $5,00 + Maquinaria $7,20 + Comercialización $12,00 + Interés var. $2,88 + Mano de obra (1,25 h) $25,00 + Mortandad $23,91 + Fijos $22,40 = Costo Total $2.548,12 USD/cab | 5) Backgrounding Verano (Pastura): Compra (525 lb a $4,92/lb) $2.583,00 + Interés (5 m) $76,52 + Pastura/supl. $93,45 + Sanidad $5,00 + Maquinaria $6,80 + Comercialización $12,00 + Interés var. $1,74 + Mano de obra (1 h) $20,00 + Mortandad $27,29 + Fijos $3,36 = Costo Total $2.829,16 USD/cab",
        "unidad": "USD/cabeza",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 11-14)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Novillos terminados (Iowa/Minnesota Choice Steers, all grades) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) en USD/cwt (1 cwt = 45,359 kg)",
        "valor": "2024: Ene 175,10 ($3,86/kg), Feb 181,24 ($4,00/kg), Mar 188,30 ($4,15/kg), Abr 185,47 ($4,09/kg), May 188,53 ($4,16/kg), Jun 195,31 ($4,31/kg), Jul 197,06 ($4,34/kg), Ago 190,56 ($4,20/kg), Sep 183,85 ($4,05/kg), Oct 188,68 ($4,16/kg), Nov 187,09 ($4,12/kg), Dic 193,82 ($4,27/kg) [Prom. 2024: 187,92 USD/cwt = $4,14/kg] | 2025: Ene 205,39 ($4,53/kg), Feb 203,35 ($4,48/kg), Mar 208,47 ($4,60/kg), Abr 215,00 ($4,74/kg), May 228,29 ($5,03/kg), Jun 237,25 ($5,23/kg), Jul 238,92 ($5,27/kg), Ago 243,58 ($5,37/kg), Sep 238,28 ($5,25/kg), Oct 235,40 ($5,19/kg), Nov 220,13 ($4,85/kg), Dic 225,76 ($4,98/kg) [Prom. 2025: 224,99 USD/cwt = $4,96/kg]",
        "unidad": "USD/cwt (y USD/kg vivo)",
        "fuente": "Iowa State University Extension / USDA AMS LM_CT185 - File B2-12: Historical Cattle Prices (Pág. 1, Table 1, Feb 2026)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Terneros de invernada (Iowa Medium & Large Frame #1, 500-600 lb Steers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026",
        "valor": "2024 (USD/cwt): Ene 286,68 ($6,32/kg), Feb 309,77 ($6,83/kg), Mar 333,48 ($7,35/kg), Abr 324,06 ($7,14/kg), May 337,77 ($7,45/kg), Jun 320,30 ($7,06/kg), Jul 326,06 ($7,19/kg), Ago 300,50 ($6,62/kg), Sep 296,44 ($6,54/kg), Oct 296,60 ($6,54/kg), Nov 311,96 ($6,88/kg), Dic 332,23 ($7,32/kg) [Prom. 2024: 314,65 USD/cwt = $6,94/kg] | 2025 (USD/cwt): Ene 345,81 ($7,62/kg), Feb 353,55 ($7,79/kg), Mar 369,84 ($8,15/kg), Abr 375,34 ($8,27/kg), May 399,91 ($8,82/kg), Jun 408,30 ($9,00/kg), Jul 399,87 ($8,82/kg), Ago 449,83 ($9,92/kg), Sep 460,84 ($10,16/kg), Oct 454,61 ($10,02/kg), Nov 413,43 ($9,11/kg), Dic 446,07 ($9,83/kg) [Prom. 2025: 406,45 USD/cwt = $8,96/kg] | Presupuesto 2026 (File B1-21): $4,92/lb = 492,00 USD/cwt ($10,85/kg)",
        "unidad": "USD/cwt (y USD/kg vivo)",
        "fuente": "ISU Extension / USDA-IA Dept of Ag Market News LSD_MARS_2167 - File B2-12 (Pág. 3, Table 3) y File B1-21 (Pág. 2)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Novillitos de recría (Iowa Medium & Large Frame #1, 700-800 lb Steers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026",
        "valor": "2024 (USD/cwt): Ene 237,00, Feb 255,83, Mar 268,67, Abr 262,99, May 271,73, Jun 269,92, Jul 276,99, Ago 260,58, Sep 260,32, Oct 259,81, Nov 263,25, Dic 274,02 [Prom. 2024: 263,43 USD/cwt = $5,81/kg] | 2025 (USD/cwt): Ene 285,92, Feb 289,60, Mar 299,77, Abr 303,87, May 321,58, Jun 333,25, Jul 337,78, Ago 373,20, Sep 379,43 ($8,36/kg), Oct 375,15, Nov 339,48, Dic 363,28 [Prom. 2025: 333,53 USD/cwt = $7,35/kg] | Presupuesto 2026 (File B1-21): $3,74/lb = 374,00 USD/cwt ($8,25/kg)",
        "unidad": "USD/cwt (y USD/kg vivo)",
        "fuente": "ISU Extension / USDA-IA Dept of Ag Market News - File B2-12 (Pág. 4, Table 4) y File B1-21 (Pág. 2)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Terneras 500-600 lb y Vaquillonas 700-800 lb (Iowa Medium & Large Frame #1 Heifers) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025) y proyección 2026",
        "valor": "Heifers 500-600 lb (USD/cwt): 2024: Ene 244,74, Feb 269,36, Mar 285,18, Abr 286,62, May 296,66, Jun 285,94, Jul 281,76, Ago 275,62, Sep 272,85, Oct 268,82, Nov 275,13, Dic 298,93 (Prom. 278,47 = $6,14/kg); 2025: Ene 308,80, Feb 314,19, Mar 324,20, Abr 333,49, May 353,77, Jun 363,13, Jul 363,65, Ago 385,64, Sep 412,88 ($9,10/kg), Oct 395,67, Nov 366,18, Dic 392,13 (Prom. 359,48 = $7,93/kg); Presupuesto 2026 (400-500 lb): $4,84/lb = 484,00 USD/cwt ($10,67/kg) | Heifers 700-800 lb (USD/cwt): 2024: Ene 215,01, Feb 229,90, Mar 238,63, Abr 236,47, May 245,90, Jun 244,31, Jul 254,06, Ago 240,64, Sep 237,06, Oct 245,50, Nov 239,78, Dic 249,72 (Prom. 239,75 = $5,29/kg); 2025: Ene 259,83, Feb 263,22, Mar 269,11, Abr 272,79, May 288,99, Jun 299,56, Jul 316,14, Ago 342,27, Sep 347,22 ($7,65/kg), Oct 343,83, Nov 314,98, Dic 328,99 (Prom. 303,91 = $6,70/kg)",
        "unidad": "USD/cwt (y USD/kg vivo)",
        "fuente": "ISU Extension / USDA-IA Dept of Ag Market News - File B2-12 (Pág. 5-6, Tables 5 & 6) y File B1-21 (Pág. 2)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Vacas de descarte (Breaking Utility Cows, 75-80% lean, Joplin MO / Midwest) - Serie mensual de 24 meses (Enero 2024 a Diciembre 2025)",
        "valor": "2024 (USD/cwt): Ene 102,35, Feb 109,15, Mar 125,17, Abr 129,09, May 130,51, Jun 137,90, Jul 141,14 ($3,11/kg), Ago 139,81, Sep 125,56, Oct 120,51, Nov 114,28, Dic 111,60 [Prom. 2024: 123,92 USD/cwt = $2,73/kg] | 2025 (USD/cwt): Ene 126,22, Feb 135,97, Mar 136,10, Abr 143,00, May 146,81, Jun 153,02, Jul 157,07, Ago 166,39 ($3,67/kg), Sep 163,47, Oct 158,45, Nov 153,11, Dic 154,03 [Prom. 2025: 149,47 USD/cwt = $3,30/kg] | Serie mensual de 24 meses para vientre preñado (bred cow/heifer): SIN FUENTE (en File B1-21 de junio 2026 se valúa la vaca de cría y la vaquillona preñada de reposición en $2.300,00 USD/cabeza)",
        "unidad": "USD/cwt y USD/cabeza",
        "fuente": "ISU Extension / USDA Market News - File B2-12 (Pág. 2, Table 2) y File B1-21 (Pág. 16)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "6. Precios por categoría",
        "dato": "Estacionalidad de precios por categoría en Iowa (2024-2025)",
        "valor": "Novillos terminados (Choice steers): pico en julio-agosto ($197,06/cwt en jul-2024, +4,9% sobre media anual; $243,58/cwt en ago-2025, +8,3% sobre media anual) y piso en enero o septiembre | Vacas de descarte (Utility cows): pico en julio-agosto ($141,14/cwt en jul-2024, +13,9% sobre media; $166,39/cwt en ago-2025, +11,3% sobre media) y piso en noviembre-enero por el descarte otoñal post-destete | Terneros 500-600 lb y feeders 700-800 lb: picos en mayo (salida a pasto: $337,77/cwt en may-2024, +7,3% sobre media) y agosto-septiembre ($460,84/cwt en sep-2025, +13,4% sobre media), con bache estacional en octubre-noviembre durante el pico de oferta de destete",
        "unidad": "USD/cwt y % sobre media anual",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B2-12 (Pág. 1-6)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b2-12.pdf",
        "fecha": "2026-02"
      },
      {
        "tema": "7. Capital",
        "dato": "Valor de una vaca de cría, un toro y un ternero de invernada, y capital inmovilizado por actividad en Iowa (2026)",
        "valor": "Vaca de cría (beef cow): $2.300,00 USD/cab | Vaquillona de reposición: $2.300,00 USD/cab ($460,00 por unidad vaca al 20%) | Toro reproductor: $5.000,00 USD/cab ($200,00 por unidad vaca a 1 toro/25 vacas) -> Inversión total en rodeo por unidad vaca: $2.960,00 USD + Instalaciones/maquinaria/alambrados (rodeo de 50 vacas): $749,00 USD/vaca = $3.709,00 USD/unidad vaca inmovilizados en forma permanente (12 meses/año, más $698,98 de costos variables por 6 meses) | Ternero de invernada: 450 lb = $2.214,00 USD/cab; 525 lb = $2.583,00 USD/cab; 550 lb = $2.706,00 USD/cab (a $4,92/lb) | Novillito yearling (750 lb a $3,74/lb): $2.805,00 USD/cab | Vaquillona yearling (700 lb a $3,74/lb): $2.618,00 USD/cab | Capital operativo y tiempos de inmovilización: Backgrounding invierno $2.525,72 var. (5 meses hacienda / 2,5 meses var.); Backgrounding verano $2.825,80 var. (5 meses / 2,5 meses); Finishing Yearling Steers $3.445,74 var. (6,5 meses hacienda / 3,25 meses var.); Finishing Steer Calves $3.547,90 var. (9 meses hacienda / 4,5 meses var.); Finishing Yearling Heifers $3.426,02 var. (270 días hacienda / 4,5 meses var.) a una tasa de interés operativo del 7,11% anual",
        "unidad": "USD/cabeza y meses",
        "fuente": "Iowa State University Extension - Ag Decision Maker File B1-21 (Pág. 2, 11-16)",
        "link": "https://www.extension.iastate.edu/agdm/livestock/pdf/b1-21.pdf",
        "fecha": "2026-06"
      },
      {
        "tema": "8. Impuestos, retenciones o tasas",
        "dato": "Tasas e impuestos sobre la hacienda y las instalaciones ganaderas en Iowa / EE.UU.",
        "valor": "National Beef Checkoff (federal): $1,00 USD por cabeza en cada venta de ganado bovino vivo doméstico o importado | Derechos de exportación (retenciones): 0% (no existen en EE.UU.) | Impuestos a la propiedad y seguros sobre instalaciones y equipos (Taxes & Insurance en presupuestos ISU): 1% anual sobre el valor de inversión original de instalaciones y equipos (dentro del 14% anual de cargo fijo = 8% depreciación + 5% interés + 1% impuestos y seguros)",
        "unidad": "USD/cabeza y % anual",
        "fuente": "Cattlemen's Beef Board / USDA AMS y ISU Extension File B1-21 (Pág. 1)",
        "link": "https://www.beefboard.org/2024/07/09/new-independent-study-finds-each-national-beef-checkoff-dollar-returns-13-41/",
        "fecha": "2024-07"
      },
      {
        "tema": "9. Riesgos",
        "dato": "Riesgos climáticos y nutricionales en Iowa y respuestas del productor",
        "valor": "Riesgos: inviernos con nieve/hielo y temperaturas bajo cero (sin crecimiento de pasturas entre noviembre y abril), sequías estivales que reducen la receptividad de las pasturas de gramíneas templadas (bluegrass/bromegrass) y estrés post-destete en terneros | Respuestas documentadas: 1) Pastoreo de rastrojos de maíz en otoño-invierno (4 acres/vaca con 3.467 lb MO/acre) y reserva de 2,1 tons/vaca de heno alfalfa-brome; 2) Preacondicionamiento y destete anticipado (early weaning de terneros de 300-500 lb) con dietas de recepción de 65-75% concentrado y 14,5% proteína bruta; 3) Sustitución entre grano de maíz, silaje de maíz y granos de destilería (MDGS/DDGS, donde 1 lb de MDGS reemplaza la energía de 0,5 lb de maíz y la proteína de 0,36 lb de harina de soja); 4) Pastoreo rotativo (+25% de producción forrajera) o envío directo de terneros a backgrounding/feedlot en confinamiento",
        "unidad": "estrategia técnica",
        "fuente": "ISU Extension File B1-21 (Pág. 11-15), File C2-23 (Pág. 2), ASL-1636 e Iowa Beef Center (Nutritional Management of the Calf after Weaning)",
        "link": "https://www.iowabeefcenter.org/Health/nutritionafterweaning.pdf",
        "fecha": "2025-08"
      }
    ]
  }
]
```
