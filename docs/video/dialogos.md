# Los diálogos del video (4/11/2026)

Lo que se ve en el video, tal cual: lo que escribe el productor y lo que contesta DORA en la app pública. Las tomas las grabó [`infra/video/record.py`](../../infra/video/record.py) y el video lo armó [`infra/video/edit.py`](../../infra/video/edit.py) con la lista de cortes y la narración de [`infra/video/scenes.py`](../../infra/video/scenes.py). Para repetirlas: `.venv/Scripts/python.exe infra/video/record.py chat_es chat_en` (las cifras pueden cambiar con los precios del día).

En la toma en español se mandan la factura [`media/factura.png`](media/factura.png) y la nota de voz [`media/nota-de-voz.wav`](media/nota-de-voz.wav), que dice: *"Tengo quinientas hectáreas y ochenta mil dólares, y un silo propio donde entran mil quinientas toneladas de grano. ¿Cuál es el valor presente?"*

Cada evento con su hora está en [`toma-chat-es.json`](toma-chat-es.json) y [`toma-chat-en.json`](toma-chat-en.json).

## Entrevista (español, Muse Spark 1.3 por la API de Meta)

**Productor** (8 s): Tengo 500 ha en Balcarce y 50.000 USD de capital. ¿Qué me conviene sembrar? Preguntame lo que necesites.

**DORA** (35 s):

> ✅ verificado: cada número sale del motor
>
> Entendí: 500 ha en Balcarce y 50.000 USD de capital.
>
> ¿El campo es propio o alquilado? Si no me decís, lo calculo como propio.

**Productor** (39 s): Es propio, pero lo quiero sembrar yo.

**DORA** (60 s):

> ✅ verificado: cada número sale del motor
>
> Anotado que es propio y lo sembrás vos, el plan queda igual.
>
> ¿Hasta cuánto te presta el banco? Si no lo sabés, sigo con un supuesto del modelo.

**Productor** (64 s): El banco me presta hasta 30000 USD.

**DORA** (76 s):

> ✅ verificado: cada número sale del motor
>
> Con ese crédito más chico el valor cae unos 13.823 USD y el plan se achica a unas 38,5 ha de trigo y 177,4 ha de soja.
>
> ¿A cuántos días te deja pagar los insumos tu proveedor? Si no lo sabés, lo dejo al contado.

**Productor** (80 s): Pago al contado.

**DORA** (127 s):

> ✅ verificado: cada número sale del motor
>
> Te conviene sembrar trigo y soja, con un valor actual de 74.364 USD.
>
> Plan: 38,5 ha de trigo y 177,4 ha de soja, dejás sin sembrar 284,1 ha. Vendés unas 158 t de trigo en diciembre y unas 433 t de soja en abril.
>
> Lo que te frena:
>
> La plata entre la 2ª quincena de nov y la 2ª quincena de abr: cada dólar extra en ese tramo te rinde 34,0% en esos 5 meses.
> Un dólar más de capital propio hoy te vale 31,8 centavos más que dejarlo depositado, y un dólar más de crédito te vale 28,3 centavos más; tierra y almacenaje no te frenan, una hectárea o una tonelada más valen cero.
> Si alquilaras todo el campo te daría 262.550 USD de valor actual; sembrar vos te da menos, con un alquiler de equilibrio de 48,73 USD/ha.
>
> Lo que entendí: campo propio en Balcarce de 500 ha con 50.000 USD y 30.000 USD de crédito, que querés sembrar vos. Precios, rindes y costos de MAGyP junio-2026 y flete provisorio a Quequén. Lo calculé sin dar tierra en alquiler y al contado.
> Si conseguís plazo del proveedor, traé la oferta y lo recalculamos.

## Factura en foto

**Productor** (135 s): adjunta la foto de la factura.

**Productor** (137 s): ¿Cómo cambia el plan con estos costos?

**DORA** (193 s):

> ✅ verificado: cada número sale del motor
>
> No cambia todavía: no pude aplicar la factura al plan porque me falta a qué cultivo va.
>
> Lo que leí de la factura de Agroservicios El Ombú:
>
> Urea 20 t por 13.000 USD y MAP 10 t por 8.000 USD, las dos como fertilizante.
> IVA 2.205 USD, que no se usa como costo.
> Para dividir por hectárea usé tus 500 ha porque la factura no dice hectáreas: daría 26 USD/ha la urea y 16 USD/ha el MAP, pero sin que me confirmes las hectáreas que cubre no lo puedo usar.
>
> Todo sigue con costos de la zona; nada tuyo reemplazó todavía.
>
> Decime para contestar todo junto:
>
> ¿Para qué cultivo es la urea y el MAP, trigo, maíz u otro?
> ¿A cuántas hectáreas cubre ese fertilizante?
>
> Cuando me digas eso lo aplico y te digo cuánto cambia el valor y las hectáreas.
>
> 📑 Conciliación de Documento del Productor:
>
> Renglones:
>
> Renglón	Cultivo	Rubro	USD/ha
> Urea granulada 46-0-0 - 20 t x USD 650,00	-	fertilizante	26,00
> Fosfato monoamónico 11-52-0 - 10 t x USD 800,00	-	fertilizante	16,00
> IVA 10,5 %	-	impuesto	IVA, no es costo
>
> Falta saber para qué cultivo y cuántas hectáreas cubre la factura para compararla con la zona.

**Productor** (196 s): Es todo el fertilizante del trigo, para 150 ha.

**DORA** (218 s):

> ✅ verificado: cada número sale del motor
>
> Con tu fertilizante de trigo el plan sube a 78.227 USD de valor actual, unos 3.863 USD más que antes.
>
> Lo que usé: la urea y el MAP van todo al fertilizante del trigo para 150 ha, por 140 USD/ha contra 214 USD/ha de la zona; el IVA no entra como costo. El resto de los costos sigue con datos de la zona.
> Plan nuevo: 39,9 ha de trigo y 184,1 ha de soja, sin deuda al final. La plata te sigue apretando entre la 2ª quincena de nov y la 2ª quincena de abr, con 38,8% en esos 5 meses.
>
> Lo que te frena:
>
> Un dólar más de capital propio hoy te vale 36,5 centavos más que dejarlo depositado.
> Una hectárea más de tierra o una tonelada más de almacenaje valen cero: no son tu freno.
> La semilla, el fitosanitario y las labores del trigo y de los demás cultivos siguen con valores de la zona.
>
> Lo que entendí: campo propio en Balcarce de 500 ha con 50.000 USD y 30.000 USD de crédito, al contado. Solo el fertilizante del trigo es tuyo; el resto es de la zona.
> Si traés otra factura con cultivo y hectáreas, la sumo y recalculo.
>
> 📑 Conciliación de Documento del Productor:
>
> Renglones:
>
> Renglón	Cultivo	Rubro	USD/ha
> Urea granulada 46-0-0 - 20 t x USD 650,00	trigo	fertilizante	86,67
> Fosfato monoamónico 11-52-0 - 10 t x USD 800,00	trigo	fertilizante	53,33
> IVA 10,5 %	trigo	impuesto	IVA, no es costo
>
> Comparación con la zona:
>
> Cultivo	Rubro	Factura	Zona	Diferencia	Se usa
> trigo	fertilizante	140.0 USD/ha	214.2 USD/ha	-34.6 %	sí, confirmado por vos (-35 % contra la zona)
>
> Antes y después:
>
> 	Antes	Después
> VAN (USD)	74.364	78.227
> Hectáreas trigo	38,5	39,9
> Hectáreas soja	177,4	184,1
> Crédito máx. (USD)	30.000	30.000
>
> Diferencia de VAN: +3.863 USD

## Nota de voz

**Productor** (227 s): manda la nota de voz.

**DORA** (276 s):

> ✅ verificado: cada número sale del motor
>
> La mejor estrategia te da un valor actual de 120.354 USD.
>
> Plan: 57,7 ha de trigo y 250,0 ha de soja, dejás sin sembrar 192,3 ha. En trigo vendés unas 221 t en diciembre y guardás unas 17 t hasta julio en tu silo; en soja vendés unas 129 t en abril y guardás unas 477 t hasta julio en tu silo. Los costos del silo son provisorios.
>
> Lo que te limita:
>
> Entre la 2ª quincena de nov y la 2ª quincena de dic cada dólar extra te rinde 32,4% en ese mes.
> Un dólar más de capital propio hoy vale 37,3 centavos más que dejarlo depositado, y un dólar más de crédito vale 33,2 centavos más.
> Una tonelada más de silo vale cero: el silo no te frena; una hectárea más te vale 1,13 USD.
>
> Lo que entendí: campo propio de 500 ha con 80.000 USD y 30.000 USD de crédito, al contado, con silo propio de 1.500 t. Precios, rindes y costos de MAGyP; el fertilizante del trigo es de tu factura y los costos del silo son provisorios.
> Si querés, decime qué banco o proveedor te ofrece y vemos si te deja sembrar más.

## En inglés, Muse Spark Open (Baseten): ¿sembrar o alquilar?

**Productor** (9 s): I have 500 ha in Pergamino and 100,000 USD. Should I farm it or rent it out? Ask me what you need.

**DORA** (64 s):

> ✅ verified: every number comes from the engine
>
> With your 500 ha in Pergamino and USD 100,000 of own capital, you are better off renting it all out: USD 385,000 of present value vs USD 258,242 if you farm it — a gain of USD 126,758 by renting.
>
> Plan the model chooses:
>
> You rent out 500.0 ha and farm 0 ha — no crop is sown.
> You collect about USD 285,000 of rent income over the season at the regional rent of USD 570/ha.
> If you insisted on farming, the rent that would make farming and renting equal is only USD 316.48/ha — any offer above that, renting pays more.
>
> What limits you:
>
> Rent beats farming at current margins — an extra hectare rented out is worth USD 570 to you, exactly the market rent. Farming 500 ha in the core Pampas around Pergamino, Rojas and Colón doesn't beat that with today's costs and prices.
> Cash is not your bottleneck — one more dollar of own capital is worth USD 0.00 beyond keeping it deposited at 4%.
> Storage is not your bottleneck — one more tonne of storage is worth USD 0.00.
>
> What I understood:
>
> Yours: 500 ha of owned land in Pergamino that you can farm or rent out, USD 100,000 own capital, all four summer/winter crops allowed.
> From regional data: MAGyP June-2026 margins for the core Pampas around Pergamino (corn 9.5 t/ha at USD 183/t, soybean 3.8 t/ha at USD 327/t, wheat 4.5 t/ha at USD 208.5/t) and regional rent USD 570/ha from Márgenes Agropecuarios / Bolsa de Rosario.
> Model assumption: owned land that can be rented out, 14.5-month season May 2026 to July 2027, with a USD 100,000 credit line at 10% available if needed.
>
> If you have an actual tenant bid in USD/ha or in qq/ha of soybean, tell me the number and I update the comparison with your offer.

## Precio de equilibrio del maíz

**Productor** (72 s): At what price would corn be worth sowing?

**DORA** (114 s):

> ✅ verified: every number comes from the engine
>
> Corn is not worth sowing at today's price — you need USD 214.50/t at the port in late March vs USD 183.00/t today (+17.2%) for the first hectare of corn to enter.
>
> That's the verified entry price, with everything else held constant. At that price the first hectare just beats renting the land out at USD 570/ha. If price goes higher, you would sow more and the plan changes.
> Price needed stays similar if you sell later: USD 215.28/t in early April, up to USD 220.84/t in late July. Best window to sell that crop is early July (year 2) at USD 220.04/t vs USD 188.18/t today (+16.9%).
> In plain words: for any selling fortnight, the whole price curve needs to be about USD 31.50/t higher across the season for corn to beat the rent.
>
> This is the port price. Farm-gate is port minus freight and marketing — so you need that rise at your buyer too.
>
> If you have a forward corn offer for March-July, give me the USD/t and I check it against that USD 214.50/t bar.
