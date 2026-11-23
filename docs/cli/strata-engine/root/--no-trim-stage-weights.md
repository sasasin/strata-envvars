# `--no-trim-stage-weights`

調査対象: Strata commit `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

| 項目 | 内容 |
| --- | --- |
| ツール ID | `strata-engine` |
| コマンド | `strata generate` |
| オプション | `--no-trim-stage-weights` |
| 別名 | なし |
| 値 | 値を取らないフラグ |

## 役割

複数 GPU の layer split で、各 GPU が担当層以外の dense weight を保持する従来の配置を選びます。通常の split trim が有効なら各カードは自分の層の dense weight だけを保持し、空いた VRAM は expert cache に回ります。このオプションを指定すると、その trim 要求を無効にします。ただし、VRAM が足りない場合に別の spill walk が後段 GPU の weight を自動 trim する経路があり、このフラグだけではその救済動作を止めません。 (`engine/src/program/generate.cpp:1150-1152`, `engine/src/program/generate.cpp:5804-5814`, `engine/src/program/generate.cpp:6041-6074`)

## 使い方

```sh
# layer split を明示して、通常の stage weight trim を無効にする
strata generate --pack /path/to/pack --tokens "1,2,3" --serve --layer-split 24 --no-trim-stage-weights
```

`--layer-split` と複数 GPU の利用がない場合、通常の trim は適用されないため、このオプションの効果もありません。例は `strata generate` の usage にある `--pack`、`--tokens` と、同コマンドの layer split 引数構造に沿っています。 (`engine/src/program/generate.cpp:1206-1215`, `engine/src/program/generate.cpp:4115`)

## 値と既定値

- 値は不要です。parser は引数を消費せず、指定すると `trim_stage_weights=false`、`trim_stage_flag=0` にします。数値や文字列を付ける形式ではありません。 (`engine/src/program/generate.cpp:4115`)
- `trim_stage_flag` の初期値は `-1`（明示指定なし）、`trim_stage_weights` の初期値は `true` です。現行実装では layer split 時に trim が既定で有効です。 (`engine/src/program/generate.cpp:1150-1152`, `engine/src/program/generate.cpp:5804-5814`)
- 値の validation はありません。オプション名の後ろに独立した値を置けば、通常の引数解析で未知引数として扱われ、usage を stderr に出して終了コード `2` になります。 (`engine/src/program/generate.cpp:4263-4268`)
- `--trim-stage-weights` と併記した場合は、argv の処理順で最後に現れた方が `trim_stage_flag` を設定します。`--trim-stage-weights` は `STRATA_STAGE_TRIM=0` より優先されますが、後から `--no-trim-stage-weights` を置けば flag は `0` になります。 (`engine/src/program/generate.cpp:4038`, `engine/src/program/generate.cpp:4115`, `engine/src/program/generate.cpp:5808-5814`)

## 実行時の動作

通常の明示 layer split では、trim が有効なとき CUDA0 の読み込み対象を担当層に絞り、後段 stage も split 範囲外の dense weight を除外します。trim を無効にするとこの通常経路が選ばれず、全層分の dense weight を保持する従来配置になります。trim が行われる経路では、PLE tensor は各カードに残し、層別 weight を読み直して担当範囲に絞ります。 (`engine/src/program/generate.cpp:5923-5954`, `engine/src/program/generate.cpp:6901-6929`, `engine/src/program/generate.cpp:7528-7554`)

`STRATA_STAGE_TRIM` との関係は次のとおりです。

| 指定 | 通常の trim 設定 |
| --- | --- |
| オプションも環境変数もなし | split 時に有効 |
| `STRATA_STAGE_TRIM=1` など、空でなく `0` 以外 | 有効 |
| `STRATA_STAGE_TRIM=0` | 無効 |
| `--no-trim-stage-weights` | 無効。環境変数が有効値でもこの明示指定が優先 |
| `--trim-stage-weights` | 有効。`STRATA_STAGE_TRIM=0` より優先 |

この表は通常の trim 要求の判定です。明示 `--no-trim-stage-weights` は `trim_user_asked` を偽にするため、メモリ不足時の spill walk が独立に trim を選ぶことがあります。現行コードでは、spill walk は `STRATA_SPILL_OFF` が未設定で、かつ `STRATA_STAGE_TRIM=0` でもない場合に判定されます。従って、`--no-trim-stage-weights` 単独ではこの自動 trim を抑止しません。`--layer-split auto` では、起動前の早期 spill walk も別経路で判定されます。 (`engine/src/program/generate.cpp:5811-5814`, `engine/src/program/generate.cpp:5826-5828`, `engine/src/program/generate.cpp:6041-6074`)

## 適用条件と副作用

- 通常の効果は複数 GPU の layer split に限られます。単一 GPU ではこの否定形に固有の警告や追加処理はありません。対照的に、肯定形 `--trim-stage-weights` は単一 GPU で無視される旨を stderr に出します。 (`engine/src/program/generate.cpp:5923-5929`)
- trim を無効にすると、各 GPU が担当外を含む dense weight を保持し、trim によって空くはずの VRAM は使えません。これは expert cache に使える領域を減らし得ます。実際の容量・性能差はモデルと GPU の状態に依存し、この調査では測定していません。 (`engine/src/program/generate.cpp:6896-6901`)
- 通常の trim 経路で再確保や再読み込みに失敗すると、stderr にエラーを出し終了コード `1` で戻る箇所があります。オプションで trim を無効にした場合、その trim 用 reload は行いませんが、通常の weight load や GPU memory 不足など他の失敗は引き続き起こり得ます。 (`engine/src/program/generate.cpp:7530-7554`, `engine/src/program/generate.cpp:7563-7568`)
- `engine/sycl/src/program/generate.cpp` には `--trim-stage-weights` の登録がありますが、この revision で確認した parser 範囲には `--no-trim-stage-weights` の登録がありません。従って、この否定形を受理する根拠は `engine/src/program/generate.cpp` の実装に限られ、SYCL 実装への適用は確認できません。 (`engine/sycl/src/program/generate.cpp:666-668`, `engine/sycl/src/program/generate.cpp:2039`)

## 出力とエラー

このフラグ単独で成功時に出す専用メッセージは確認できません。肯定形の trim が単一 GPU で無視される場合の警告、および spill walk がメモリ不足を検知した場合の診断は、それぞれ別条件の出力です。 (`engine/src/program/generate.cpp:5923-5929`, `engine/src/program/generate.cpp:6062-6067`)

引数に値を付けるなどして未知引数となる場合は、`unknown argument: ...` と usage を stderr に出し、終了コード `2` で終了します。 (`engine/src/program/generate.cpp:4263-4268`)

## 根拠

- `engine/src/program/generate.cpp:1150-1152` — trim の初期値と flag の状態。
- `engine/src/program/generate.cpp:4038`, `engine/src/program/generate.cpp:4115` — 肯定形・否定形の parser 登録。
- `engine/src/program/generate.cpp:5804-5814` — split 時の既定値、環境変数との優先順位、trim 要求の判定。
- `engine/src/program/generate.cpp:5923-5954` — 明示 split の trim 条件と CUDA0 の担当範囲設定。
- `engine/src/program/generate.cpp:6041-6074` — メモリ不足時 spill walk の別判定と後段 trim 条件。
- `engine/src/program/generate.cpp:6901-6929`, `engine/src/program/generate.cpp:7528-7575` — VRAM 解放量の計算、担当層だけを保持する reload と診断出力。
- `engine/src/program/generate.cpp:4263-4268` — 未知引数の出力と終了コード。
- `engine/sycl/src/program/generate.cpp:666-668`, `engine/sycl/src/program/generate.cpp:2039` — SYCL parser には肯定形のみが確認できた範囲。
