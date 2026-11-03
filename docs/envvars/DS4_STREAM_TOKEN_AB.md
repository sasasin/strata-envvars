# `DS4_STREAM_TOKEN_AB`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

DS4.1 の decode で、PCIe lane が CPU lane の expert を GPU に stream する場合に、streaming を使う token と CPU lane だけで処理する token を交互に計測します。全 step の時間を比べ、streaming が遅いと判定した場合は、その実行中の streaming を止め、GPU ごとの lane 状態を times file に `off` として保存します。

これは DS4 の PCIe lane 用 A/B 判定です。環境変数自体は `src/dsv41/ds4_model.cu` の `tok_ab_active()` から読みます。同ファイル内の候補名の参照はこの読み取りと説明コメントだけでした。

## 値と判定

値は初回の `tok_ab_active()` 呼び出し時に `std::getenv` と `std::atoi` で判定され、関数内の `static const bool` に保存されます。

| 環境変数の状態 | 判定 |
| --- | --- |
| 未設定 | 有効 |
| `atoi(value)` が 0 | 無効 |
| `atoi(value)` が 0 以外 | 有効 |

空文字、数字に変換できない文字列は `atoi` の結果が 0 となるため無効です。`atoi` は文字列全体の厳密な数値検証ではありません。先頭の空白や符号の後に数字があればその数値部分を変換し、数字以降の文字は無視します。たとえば `1abc` は有効、`0abc` と `abc` は無効です。変換可能な上限・下限を Strata 側で検査したり clamp したりしません。

この変数に CLI 引数や設定ファイル値による上書きはありません。別の変数 `DS4_STREAM`（未設定時は `STRATA_DS4_STREAM`）は PCIe lane 自体を許可する条件に関わりますが、この変数の parse 値を変更しません。

## 有効になる条件

この A/B 判定が有効でも、DS4 の PCIe lane が実際に stream 可能な状態でなければ効果はありません。

- 対象は DS4.1 モデルの decode `step()` 経路です。prompt の chunk 処理ではなく、1 token の `forward()` の前後で判定します。
- `DS4_STREAM` が無効でないこと。`DS4_STREAM` が未設定なら `STRATA_DS4_STREAM` を参照し、両方未設定または `atoi(value) == 0` なら lane は無効です。`DS4_STREAM=2` は slot を保持しても stream しない経路です。
- GGUF、`moe_token_path`、非同期 decode（`sync_decode` でない）であること。lane の設定時にこれらを満たさない場合は lane allocation を行いません。
- stream 対象 layer は MXFP4、単一 GPU member、expert 数が `1..kPicks`、正の blob size であり、VRAM に全 expert が収まらず、lane 用領域や pinned host memory 等の確保・デバイスアクセスが成功している必要があります。
- 計測後、cost が有効で、split の計画と既存 `LaneAB` verdict が許可して `LaneCls::stream` になったクラスが必要です。times file が当該 GPU の lane を `off` と記録している場合は、通常 slot の確保も省かれます（`DS4_STREAM_FORCE` が設定されている場合を除く）。
- `DS4_STREAM_FORCE` が設定されていると `tok_ab_active()` は false になり、この A/B 比較を行いません。

CUDA API を使う DS4 実装上の機能です。`one_gpu_path()` は `STRATA_USE_HIP` ビルドで自動有効にしない条件分岐がありますが、この変数の読み取り自体には OS/backend 別の値判定はありません。HIP での lane 適用可否は、このソース調査だけでは一般化できません。

## 実行時の詳細

`step()` は `forward(&token, 1, ...)` の前に `tok_ab_begin()`、成功結果を得た後に `tok_ab_end(1, ok)` を呼びます。A/B 判定が有効で、stream 対象クラスが存在し、強制指定がない場合、decode step を 8 token ずつ streaming 側と CPU lane のみ側に交互に割り当てます。`serve_lane()` は CPU-only 側の turn を示す `tok_ab_off` を見て、split が選んだ expert mask を 0 にします。したがってこの判定はログだけでなく、その step で PCIe lane が取る expert を制御します。

成功した step の時間と token 数を各 arm に加算し、各 arm 64 token 以上で平均時間を比較します。最初の比較は warm-up として判定に使わず、その後は streaming 側が 3% 以上速い比較が連続 2 回なら「速い」、それ以外の比較が連続 2 回なら「遅い」とします。判定が決まらないまま 9 回の比較に達した場合も遅い扱いです。比較の各 arm の累積値は比較後にリセットされます。

streaming が速いと決まると、この A/B 機能は以降の step では無効になり、既存 lane 判定に任せます。遅い、または上限到達で streaming を止める場合は、以降の step の `tok_ab_off` を立て、各 stream 対象 GPU の lane key に `off` を `lane_put()` で保存します。保存先は `DS4_LANE_CAL` が unset なら `<pack>/lane-times.txt`、`none` なら保存なし、それ以外なら指定パスです。これはモデル実行中の `TokAB` 判定状態とは別の永続化です。

環境変数の有効・無効値はプロセス内の最初の判定時に static cache されます。`TokAB` の測定カウンタと verdict はモデル実行インスタンスの状態で、別プロセスの起動時には新たに初期化されます。値の変更を実行中に反映する再読込はありません。

観測できる結果として、判定時に stderr に `ds4: PCIe lane: decode measured whole steps with the split against the CPU lane alone: ... -> it streams` または `... -> it no longer streams (kept for the next start)` が出ます。遅い判定では、保存対象 GPU の lane を `off` にします。比較中は `tok_ab_off` による turn ごとの切替が行われますが、各 step の切替だけを示す専用ログはありません。判定不能・失敗時の timeout や終了処理はこの変数の実装にはありません。

## 根拠

- `src/dsv41/ds4_model.cu:10154-10173` — `TokAB` 状態、環境値の parse と cache、適用条件。
- `src/dsv41/ds4_model.cu:10175-10220` — arm の交互割当、64 token ごとの比較、閾値・ログ・lane の `off` 保存。
- `src/dsv41/ds4_model.cu:11374-11380` — decode step ごとの開始・終了と成功条件。
- `src/dsv41/ds4_model.cu:9934-9956` — `tok_ab_off` による streamed expert mask の抑止。
- `src/dsv41/ds4_model.cu:9711-9725,9753-9756,9775-9795,10431-10467,10591-10642` — `DS4_STREAM` 優先順位、lane の設定・適用条件、times file の扱い。
- `docs/DEEPSEEK41.md` と `docs/DETAILS.md` には候補名 `DS4_STREAM_TOKEN_AB` の個別説明は見つかりませんでした。実装コメントの説明は上記の現行コードと照合しました。
