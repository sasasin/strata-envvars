# `--lookup-chain`

調査対象: Strata commit `9f7d977d220e9fdf2ec53cf2620cdadac1cfb24e`（2026-11-06 調査）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | ネイティブ `strata` エンジン（`generate` / `--serve` のデコード設定） |
| オプション | `--lookup-chain` |
| 別名 | なし |
| 値 | 整数 K。`atoi` で読み取り、0〜7 に丸める。既定値 0（無効） |

## 役割

MTP（またはそのデコード窓で使われるドラフト）の提案に続けて、直前の文脈とドラフト列が過去に現れた箇所の続きを prompt lookup で最大 K 個提案し、同じ検証窓に加えます。窓サイズ上限は 8 トークンです。既定では無効です（`src/program/generate.cpp:977-980,1160-1162`）。

## 使い方

```sh
strata --native model.gguf --mtp model-mtp.gguf --spec 4 --lookup-chain 2
```

サーバーモードでは同じエンジン引数に `--serve` を付けます。

```sh
strata --native model.gguf --mtp model-mtp.gguf --spec 4 --lookup-chain 2 --serve
```

## 値と既定値

- 値は必須です。値が欠けると `--lookup-chain needs a value` を stderr に出して終了コード 2 になります（`src/program/generate.cpp:3370-3372`）。
- 初期値は 0 です。指定値は `std::atoi` で整数化した後、0 未満を 0、7 超を 7 に丸めます。したがって負数は無効化、8 以上は 7 として扱われます。`atoi` のため厳密な整数形式 validation はなく、変換結果をそのまま丸めます（例: 数字で始まらない文字列は 0）。値自体に専用の validation error はありません（`src/program/generate.cpp:977-980,3625`）。
- 窓の拡張は `--spec >= 2` の場合だけ設定され、`--mtp-max-t` と現在の `--spec` に基づいて上限 8 まで拡張します。実際の提案数は K だけでなく、検証窓の残り容量と lookup の結果でも制限されます（`src/program/generate.cpp:4304-4311,18649-18654`）。

## 実行時の動作

有効値が 1 以上なら、各リクエストの開始時に prompt の token 列で suffix 履歴と追加 draft source を初期化し、生成結果として確定した token を追加 source に逐次追加します（`src/program/generate.cpp:17778-17785,18954-18956`）。各デコード反復では、初回窓、既に suffix lookup 由来の窓、または現在の窓に空きがない場合は chained lookup を行いません。それ以外では suffix 履歴の末尾（保留中ドラフトを含め最大 64 token）を検索キーとし、過去の一致箇所に続く token を最大 K 個提案します（`src/program/generate.cpp:1310-1312,1339-1346,18647-18654`）。

提案は MTP の提案後に続けて窓へ足され、通常の verifier が窓全体を検証します。チェーン部分の受理 token 数は MTP 部分と別に計数されます（`src/program/generate.cpp:18647-18654,18665-18667,18890`）。

既定では起動後の実測コストと一致率を使う `DraftPolicy` が追加数を選び、採算が見込めないと判断した提案は使わないことがあります。`STRATA_LOOKUP_CHAIN_FIXED` が環境に存在するとこの policy gate を通さず、見つかった提案を窓へ追加します（`src/program/generate.cpp:17807,18655-18660`; `src/spec/draft_policy.cpp:285-305`）。この環境変数の有無判定は値の内容を見ません。

`--lookup-chain` 有効時は `--lookup-max-t` の未指定時既定値を決める入力にも chain 有効状態が渡されます。また、`--lookup-chain` は `--lookup-max-t` の自動既定選択で従来窓を維持する条件に含まれます（`src/program/generate.cpp:4284-4298`）。`--lookup-chain-min M`（既定 3）は拡張対象とする最短一致長を調整し、3 未満の値は 3 に丸められます（`src/program/generate.cpp:981,3626`）。

## 適用条件と副作用

- オプションは `src/program/generate.cpp` の共通引数 parser で受け付けられます。ソース上、単発 `generate` と `--serve` の双方に専用のチェーン提案・受理集計処理があります（`src/program/generate.cpp:3258,18649-18660,20439,20604-20617`）。
- 有効化すると各リクエストの prompt と確定 token をメモリ上の suffix / draft source 履歴に追加します。ファイル書き込みやネットワーク通信をこのオプション自体が行う処理は確認できません（`src/program/generate.cpp:17778-17785,18954-18956`）。
- 窓は最大 8 token です。追加候補が得られない、最短一致に達しない、窓の空きがない、または policy が採用しない場合は chained draft が追加されません（`src/program/generate.cpp:18649-18660`; `src/spec/draft_source.cpp:13-35`）。
- `STRATA_SPEC_PROB=1` のときチェーン提案を有効にすると gated proposal の条件を満たさず、この経路では従来の判定へ戻る warning が出ます（`STRATA_SPEC_PROB` が無効ならこの warning 分岐は呼ばれません）（`src/program/generate.cpp:3137-3154,17550-17553`）。

## 出力とエラー

serve では各リクエストの `DONE` 行に chain accepted/offered 等の追加カウンタが付き、処理終了時には stderr に `strata serve: lookup chain: ...` の集計が出ます（`src/program/generate.cpp:19269-19285,19588-19590`）。単発 `generate` では終了時の stdout summary に `lookup chain` の窓数と受理数が出ます（`src/program/generate.cpp:20719,20790-20793`）。

`--lookup-chain` 自体について確認できた parser エラーは値欠落時の終了コード 2 です。指定値の範囲外はエラーではなく丸められます。検証窓実行など後続処理で起きる失敗は通常の `ERR` 出力経路を通り、option 固有のエラーとは区別されます（`src/program/generate.cpp:3370-3372,18853-18860`）。

## 根拠

- parser と値の保存: `src/program/generate.cpp:977-980,3625`
- help と既定の説明: `src/program/generate.cpp:1160-1162`
- 窓サイズ調整・上限: `src/program/generate.cpp:4304-4311`
- prompt / 確定 token 履歴、提案条件と policy: `src/program/generate.cpp:1310-1312,1339-1355,17778-17785,17807,18647-18667`; `src/spec/draft_source.cpp:13-35`; `src/spec/draft_policy.cpp:285-305`
- verifier と chain 計数: `src/program/generate.cpp:18853-18860,18890,19269-19285,19588-19590,20719,20790-20793`
- `STRATA_SPEC_PROB` との適用制約: `src/program/generate.cpp:3137-3154,17550-17553`
