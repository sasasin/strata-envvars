# `STRATA_Q36_PEER_SWAP_QUIET`

調査対象: Strata `main` の HEAD `73d4f4196c25a65e02f6b9ef25d354826ce55105`（`2026-11-23` 時点）。

## 役割

Qwen3.6 エンジンの peer expert tier が expert slot を入れ替えたときに出す、swap ごとの stderr 行を抑制する診断用スイッチ。変数を設定すると `show` が false になり、`strata-q36: peer swap L...` の行を出さなくなる。slot の選定、コピー、swap 数、集計値はこの変数では変わらない。根拠: `engine/src/qwen35/q36_engine.cu:3506-3524,3558-3576`。

このコードは `q36_engine.cu` に実装された Qwen3.6 エンジン経路で使われ、同じエンジンライブラリを `strata` の Qwen3.6 family と `strata-q36` が利用する。ソースは HIP gfx906 を除く GPU build でライブラリに含められる。根拠: `engine/cmake/strata_gpu_engine.cmake:565-583`。

## 値と判定

文字列の内容は parse せず、`std::getenv(...) == nullptr` かどうかだけを見る。未設定なら `show=true`、設定されていれば `show=false`。したがって空文字、`0`、`1`、`false`、大小文字の異なる文字列、前後に空白のある値はいずれも「設定あり」として swap ごとの行を抑制する。数値変換、値域、無効値 fallback はない。根拠: `engine/src/qwen35/q36_engine.cu:3524`。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| Qwen3.6 エンジンの peer tier rebalance がこの判定行に到達 | swap ごとのログを表示 | 該当なし。設定有無で判定 | 該当なし。空文字を含め、あらゆる設定値でログを抑制 |

Strata の `docs/SETTINGS.md` はこの候補を `on / off` と分類しているが、実装には on/off の文字列判定はなく、設定の有無だけで決まる（`docs/SETTINGS.md:277`、`engine/src/qwen35/q36_engine.cu:3524`）。

## 有効になる条件

- Qwen3.6 エンジン経路が使われること。`strata` ではこの family 用ライブラリ、または standalone `strata-q36` が該当する。gfx906 HIP build は CMake 上このライブラリを追加しない（`engine/cmake/strata_gpu_engine.cmake:565-583`）。
- モデルが hybrid mode であり、peer tier の compute context・arena・slot が有効であること。`peer_rebalance()` はこれらがないと早期 return する（`engine/src/qwen35/q36_engine.cu:3506-3509`）。peer tier は CLI の `--peer-device` で構成される（同: `5388-5390,4387-4396`）。
- `STRATA_Q36_PEER_FIXED` が設定されていないこと、warmup 中でないこと、decode/verify 行が保留中でないこと。これらの場合は関数が早期 return し、この変数の判定にも到達しない（同: `3510-3511`）。
- 1 rebalance あたりの swap 上限が正であること。上限は `min(max_swaps, STRATA_Q36_PEER_SWAPS)`（未設定時 4、負値は 0）で、この呼び出しの `max_swaps` は 8。上限が 0 以下なら早期 return し、quiet 判定は行われない（同: `3512-3524`、呼び出し元 `1881-1885`）。
- rebalance の対象になるのは hybrid decode/verify の確定行後、position が 32 の倍数の境界。prompt chunk ではなく、この条件に合う後続処理で swap が起きたときだけ swap ごとの行が候補になる（同: `1866-1885,3500-3504`）。

## 実行時の詳細

`after_rows()` は hybrid モードで position が 32 の倍数のとき、同期して通常 tier の `rebalance(8)` に続き `peer_rebalance(8)` を呼ぶ。peer rebalance は各 layer で、両 GPU に resident でなく routing score が正の expert を候補にし、peer slot の resident より score が高い場合に、host arena から peer GPU arena へ expert blob をコピーして slot を更新する。`STRATA_Q36_PEER_SWAP_QUIET` はこの処理の後、swap ごとの `fprintf(stderr, ...)` を囲む `show` 判定にだけ使われる（`engine/src/qwen35/q36_engine.cu:3500-3504,3531-3576`）。

`show` は関数内 `static const bool` で、先行する各 return と `per <= 0` の return を通過して初めて初期化される。初期化後、同じプロセス内で環境変数を変更しても判定は更新されない（`engine/src/qwen35/q36_engine.cu:3506-3524`）。CLI 引数や別環境変数が quiet の値を上書きする処理はない。`STRATA_Q36_PEER_FIXED` や `STRATA_Q36_PEER_SWAPS` は rebalance 自体の実行可否・swap 上限に関わる別条件であり、この変数はそれらの値を変更しない（同: `3510-3524`）。

## ログと測定値

unset で swap が成立すると、swap ごとに次の形式の行を stderr に出す。対象変数が設定されているとこの行だけが抑制される。

```text
strata-q36: peer swap L<layer>: expert <new> into slot <slot>, expert <old> out (counts <new-score> vs <old-score>)
```

swap が1件以上あれば、quiet 設定の有無にかかわらず rebalance 集計行 `strata-q36: peer tier: ...` は出力される。quiet は集計行や最後の `peer tier motion` 表示を抑制しない。根拠: `engine/src/qwen35/q36_engine.cu:3574-3587,5540-5552`。この変数に関する Strata の測定値は該当資料にない。

## 根拠

- 直接の読み取りと swap ごとの出力判定: `engine/src/qwen35/q36_engine.cu:3524,3574-3576`
- rebalance の早期 return、固定値と上限、swap 候補とコピー: `engine/src/qwen35/q36_engine.cu:3506-3524,3531-3576`
- rebalance 呼び出し周期と経路: `engine/src/qwen35/q36_engine.cu:1866-1885`
- peer tier の構成と CLI: `engine/src/qwen35/q36_engine.cu:4387-4396,5388-5390`
- ビルド対象: `engine/cmake/strata_gpu_engine.cmake:565-583`
- 設定カタログ上の分類: `docs/SETTINGS.md:277`
