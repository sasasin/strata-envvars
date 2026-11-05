# `STRATA_SPLIT_EARLY_OFF`

調査対象: Strata `main` の HEAD `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 時点）。

## 役割

`--layer-split auto` の開始前に行う、VRAM が足りない GPU を避けるための early spill walk を抑止します。この walk はモデル重みをロードする前に GPU の空き容量を見積もり、層の分割先を調整したり、容量が足りないカードを split から外したりします。環境変数が設定されていると、この事前判定ブロックを実行せず、従来の重みロード後の split 探索へ進みます（`src/program/generate.cpp:4965-4977`）。

この変数は、後段にある重みロード後の walk を無効にはしません。そこで later GPU の空き容量を調べて各カードの層重みを trim する処理は、別の条件で引き続き実行されます（`src/program/generate.cpp:5186-5219`）。

## 値と判定

数値や文字列の値は parse しません。`std::getenv(...) == nullptr` かどうかだけを判定します。

| 設定状態 | 判定 | 効果 |
|---|---|---|
| 未設定 | `getenv` が null | 他の条件も満たす場合、early walk を実行可能 |
| 設定済み（空文字を含む） | `getenv` が非 null | early walk を抑止 |

`1`、`0`、`false` などの文字列内容は区別されません。空白、大小文字、数値としての妥当性も調べません。空文字を含め、何らかの値が環境に存在するだけで抑止します（`src/program/generate.cpp:4971-4973`）。

## 有効になる条件

未設定であっても、early walk は次の条件をすべて満たす場合に限り実行されます。

- 複数 GPU の実行である（`multi_gpu`）。
- `--layer-split auto` の自動分割経路である（`split_auto`）。
- `--trim-stage-weights` などで trim が要求されていない（`!trim_asked`）。
- 分割対象 GPU がある（`!split_devs.empty()`）。
- `STRATA_SPILL_OFF` が未設定。
- `STRATA_STAGE_TRIM` が、設定済みの文字列全体が `"0"` となる状態ではない。
- `spill_discrete_gpu()` が true。これは Metal では spill 許可判定を使い、それ以外では現在の CUDA device の取得と device properties の確認を行い、integrated GPU ではないことなどを `strata::spill_allowed` で判定します（`src/program/generate.cpp:276-289`）。

したがってこの変数は `--layer-split auto` 以外や単一 GPU では実質的に影響しません。`STRATA_SPILL_OFF` や `STRATA_STAGE_TRIM=0` が early walk を抑止する場合もあります。反対に、`STRATA_SPLIT_EARLY_OFF` が設定されていても、重みロード後の別 walk（`src/program/generate.cpp:5191-5192`）や明示的な trim の処理まで止めるものではありません。

## 実行時の詳細

値は `generate` の split 初期化中、early walk の条件式で直接読み取られます。`static` cache はなく、この判定はその条件式が評価される時点のプロセス環境を参照します。対象経路では、設定があれば early walk の pool 見積もり、GPU 空き容量の事前確認、層割当て調整へ入らず、通常の後続初期化に進みます（`src/program/generate.cpp:4971-5061`）。

この変数自体について、設定値を示すログ、警告、終了・失敗経路はありません。抑止により事前のカード除外・分割調整が行われないため、その後の標準 split 探索や重み確保で別の結果になる可能性はありますが、個々の結果は後段の状態によります。後段には空き容量に応じて later card の重みを trim する処理が別にあります（`src/program/generate.cpp:5186-5219`）。

## 根拠

- 候補名の全参照: `src/program/generate.cpp:4970-4973`。4970 行目は説明コメント、4973 行目が環境から値を読む唯一の実装箇所です。
- early walk の条件と初期の割当て調整: `src/program/generate.cpp:4965-5061`。
- spill 対象 GPU の判定: `src/program/generate.cpp:276-289`。
- 重みロード後に別途行う trim walk: `src/program/generate.cpp:5186-5219`。
- `docs/DETAILS.md` に本変数または early split の仕様説明は見つかりませんでした。
