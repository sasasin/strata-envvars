# `--trim-stage-weights`

調査対象: Strata commit `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata`（エンジン引数、トップレベル） |
| オプション | `--trim-stage-weights` |
| 別名 | なし。同じ設定を無効にする別オプション `--no-trim-stage-weights` がある |
| 値 | 値を取らないフラグ |

## 役割

GPU 間でモデル層を分割して実行するとき、各 GPU にその GPU が担当する層の dense weights だけを残す設定を明示します。保持しなくなった他層の dense weights 分の VRAM は expert cache に回されます。現行の CUDA/HIP 実装では layer split 時の既定動作も trim 有効です。このオプションは既定を切り替えるためというより、trim を明示して `STRATA_STAGE_TRIM=0` より優先させる場合などに使います。(`engine/src/program/generate.cpp:1151-1155`, `engine/src/program/generate.cpp:5832-5842`)

## 使い方

```sh
# 2 GPU の layer split で trim を明示する例
strata --pack ./model --gpu 0,1 --layer-split 24 --trim-stage-weights --tokens "1,2,3"
```

`--layer-split` の指定形式や分割点の意味は同オプションの文書を参照してください。`--trim-stage-weights` 自体には引数を付けません。(`engine/src/program/generate.cpp:4043`)

## 値と既定値

- 値なしの真偽フラグです。parser は指定時に `trim_stage_weights=true`、`trim_stage_flag=1` を設定します。数値や文字列の validation はありません。(`engine/src/program/generate.cpp:4043`)
- 初期値は trim 有効、明示指定状態は「未指定」です（`trim_stage_weights=true`, `trim_stage_flag=-1`）。ただし実際の trim は複数 GPU の layer split があるときに限られます。(`engine/src/program/generate.cpp:1151-1155`, `engine/src/program/generate.cpp:6929`)
- `--no-trim-stage-weights` は同じ設定を無効化します。オプション解析は引数を順に処理して値を上書きするため、両方を重ねて指定した場合は後に現れた方が parser 状態を決めます。(`engine/src/program/generate.cpp:4043`, `engine/src/program/generate.cpp:4120`)
- `STRATA_STAGE_TRIM=0` は trim を無効にしますが、明示した `--trim-stage-weights` が優先します。`--no-trim-stage-weights` を指定すると trim は無効です。(`engine/src/program/generate.cpp:5836-5842`)

## 実行時の動作

`--layer-split` が明示的な分割の場合、CUDA0 は担当層の範囲を設定して dense weights を読み、後続 GPU もそれぞれの担当範囲だけで weights を読みます。層ごとの weight 行を pack の `index.txt` から組み立て、担当外の行を除外した arena を再確保して weights を再ロードします。PLE 行は各 GPU に残す扱いです。(`engine/src/program/generate.cpp:5978-5982`, `engine/src/program/generate.cpp:6932-6953`, `engine/src/program/generate.cpp:7599-7625`)

`--layer-split auto` では分割位置が決まる前に CUDA0 の weights が読み込まれるため、後続段の読み込みを分割探索後まで遅らせ、分割判明後に各段の範囲でロードします。trim により空いた容量は分割・cache 容量の見積もりにも加味されます。(`engine/src/program/generate.cpp:5954-5959`, `engine/src/program/generate.cpp:6677-6683`, `engine/src/program/generate.cpp:6955-6957`, `engine/src/program/generate.cpp:7077`)

trim は dense weight の配置を変えるもので、ソースコメントでは trim 自体は bit-exact とされています。一方、解放した VRAM が expert cache に回るため、cache の保持内容が変わり得ます。(`engine/src/program/generate.cpp:6071-6073`, `engine/src/program/generate.cpp:6924-6929`)

## 適用条件と副作用

- 複数 GPU の layer split がない場合、このフラグによる trim は行われず、明示的に指定したときは stderr に `--trim-stage-weights needs a layer split across GPUs (ignored)` と出します。単一 GPU での指定をエラー終了にはしません。(`engine/src/program/generate.cpp:5951-5957`)
- メモリが不足する後続 GPU では、明示的に trim を要求していない場合にも spill walk が個別に trim を選ぶ経路があります。`STRATA_STAGE_TRIM=0` または `STRATA_SPILL_OFF` がある場合、この spill walk の trim 経路は無効になります。これはフラグを指定した trim とは別の自動判定です。(`engine/src/program/generate.cpp:6071-6075`, `engine/src/program/generate.cpp:6090-6102`)
- SYCL 実装にも同じ文字列の parser がありますが、そこでは既定値が false で、明示的な `--layer-split` を前提とする別実装です。本書の対象は `docs/cli/000_cli_tools.md` が `strata-engine` の parser として示す `engine/src/program/generate.cpp` です。(`engine/sycl/src/program/generate.cpp:666-668`, `engine/sycl/src/program/generate.cpp:2039`)

## 出力とエラー

- 単一 GPU で明示指定した場合、上記の無視メッセージを stderr に出します。(`engine/src/program/generate.cpp:5951-5953`)
- trim 時の weight pool 見積もりに失敗すると stderr にエラー文字列を出して `return 1` します。再ロード用 arena の割り当て、または weights / native dense のロードに失敗した場合もエラーを stderr に出して生成処理を失敗させます。(`engine/src/program/generate.cpp:6943-6950`, `engine/src/program/generate.cpp:7617-7625`, `engine/src/program/generate.cpp:7634-7639`)
- このフラグに値を余分に付けた場合、その値は別の引数として処理され、未知の引数として usage とともに stderr に出て終了コード 2 になります。(`engine/src/program/generate.cpp:3842-3849`, `engine/src/program/generate.cpp:4268-4273`)

## 根拠

- `engine/src/program/generate.cpp:1151-1155` — 初期値と明示指定状態。
- `engine/src/program/generate.cpp:4043`, `engine/src/program/generate.cpp:4120` — 有効・無効フラグの parser。
- `engine/src/program/generate.cpp:5832-5842` — `STRATA_STAGE_TRIM` と CLI 指定の優先順位。
- `engine/src/program/generate.cpp:5951-5959`, `engine/src/program/generate.cpp:6677-6683` — split 条件および `auto` での読み込み順。
- `engine/src/program/generate.cpp:6932-6957`, `engine/src/program/generate.cpp:7599-7646` — 担当外 weights の除外、再ロード、失敗経路。
- `engine/src/program/generate.cpp:6071-6102` — メモリ不足時の自動 trim 条件。
- `engine/sycl/src/program/generate.cpp:666-668`, `engine/sycl/src/program/generate.cpp:2039` — 別の SYCL parser の存在と異なる既定値。
