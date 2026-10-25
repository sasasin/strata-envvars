# `STRATA_PREFILL_HELPER_SOURCE`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-15 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--serve` の prompt prefill で、helper GPU の VRAM expert cache にある blob を、モデルファイルから読み直す代わりに host 側の prompt staging buffer へコピーします。helper cache にない blob は従来の `ExpertSource` へ渡されます。通常の `generate` 経路ではこの変数を読まず、serve 経路でも既定は無効です。

## 値と判定

`src/program/generate.cpp` は環境変数が設定されているかを確認した後、値を `std::atoi()` に渡し、結果が 0 以外かを判定します。文字列全体の厳密な検証や `1` との比較ではありません。

| 値 | 判定 |
|---|---|
| 未設定 | 無効 |
| 空文字、数字に変換できない文字列（例: `true`） | `atoi` が 0 を返すため無効 |
| 整数として 0 になる値（例: `0`, `00`, `-0`） | 無効 |
| 整数として 0 以外になる値（例: `1`, `2`, `-1`） | 有効候補 |
| 数字の後ろに文字が続く値（例: `1junk`） | 数字の prefix が 0 以外なら有効候補。文字列全体は検証しない |

`atoi` の通常の変換規則により先頭の空白と符号は許され、最初の数字以外で変換が止まります。数値範囲外の文字列の結果には依存しないでください。判定は serve 起動時の初期化で行われ、リクエストごとの再評価やプロセス起動後の環境変更を反映するコードはありません。

根拠: `src/program/generate.cpp:7244-7259`。

## 有効になる条件

値が 0 以外でも、次の条件をすべて満たしたときだけ prompt source を切り替えます。

- コマンドが `--serve` の経路に入っている。
- `srcp` が有効な expert source を指している。
- `multi_gpu` が false で、layer split がない。
- `stages` が空である。
- `o.batch <= 0` で、batch slots を使わない。
- helper の `prefill_helpers` が空でない（`drive.d.remote_count` 個の helper を列挙した結果）。

条件を満たさない場合、変数を有効値にしても source は `srcp` のままです。ソース上、この変数に対応する CLI 引数や別の環境変数による上書きはありません。helper expert cache 自体の設定・容量は別の serve 引数で決まり、この変数だけでは cache を作成しません。

## 実行時の詳細

有効条件を満たすと `RemotePrefillSource` が作られ、`Prefill::init()` に元の `srcp` の代わりに渡されます。prefill 側は helper cache に現在ある `(layer, expert)` を transient source として扱い、複数 blob の staging では helper ごとにまとめて読み取り、cache hit でない blob は元 source の `copy_blobs()` に渡します。これにより file source の batching などの fallback 処理は維持されます。通常の `generate` は別の `Prefill::init()` 呼出しで `srcp` をそのまま渡しています。

helper 側は専用 CUDA read stream で VRAM cache から host buffer へ `cudaMemcpyAsync` し、その stream を同期してから呼出し元へ戻ります。複数の prefill staging thread から読めるよう mutex で同時読取りを直列化します。cache hit はコピー時に調べられ、ラッパー側に別 cache はありません。したがって、リクエスト間に helper cache の内容が変わった場合は次の読み取り時の状態が使われます。

CUDA 読取りが失敗すると、stderr に `prefill: a helper cache read failed (%s); the file source fills that blob instead` を一度出し、失敗した blob を元 source から補います。読み取り済み hit のコピーが完了していることを確認できない場合は hit 扱いを取り消して fallback します。helper source が作られた場合、各 request の終了時に `strata serve: prefill helper source: %lld blobs / %.1f MiB taken from a helper's cache in this request` を stderr に出します。起動時には有効化した旨の行も出ます。

## 文書との照合

`docs/SECOND_GPU.md` は helper GPU cache と prompt prefill が CUDA0 で動く構成を説明しています（72-74行）が、この環境変数の個別説明はありません。`docs/DETAILS.md` の関連箇所（600-603行）は helper cache と layer split が VRAM elastic 機能の適用外であることを記載しています。今回確認したソースは cache hit 時に helper cache から prompt staging buffer へ blob をコピーする実装を示しますが、この調査では性能測定や token 結果を検証していません。

## 根拠

- 環境変数の判定、helper 列挙、適用条件、起動ログ: `src/program/generate.cpp:7244-7260`
- helper source を prompt path に渡す箇所: `src/program/generate.cpp:7608-7612`
- `generate` 経路では元の `srcp` を渡す箇所: `src/program/generate.cpp:13205-13211`
- helper cache read stream の作成: `src/core/remote_experts.cpp:195-213`
- VRAM cache から host へのコピー、同期、read lock: `src/core/remote_experts.cpp:349-379`
- cache hit の識別、fallback、1回の警告: `src/core/remote_experts.cpp:381-455`
- source wrapper の fallback semantics と transient/pinned 判定: `include/strata/core/remote_experts.hpp:104-163`
- prompt stager の複数 blob 読取り呼出し: `src/prefill/prefill.cpp:534`
- helper cache 関連の serve 構成: `docs/SECOND_GPU.md:72-74`
- docs の関連機能制約: `docs/DETAILS.md:592-603`
