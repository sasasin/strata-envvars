# `STRATA_NO_MULTI_GR`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。

## 役割

複数 token の gated-residual（GR）処理で、まとめて行う読み書きや token 数ごとに特殊化した CUDA kernel を避けるための診断・A/B 用スイッチです。設定すると、通常の `gr_read_multi` / `gr_write_multi` は可能な場合でも token ごとの `gr_read` / `gr_write` にフォールバックします。MTP の residual write も同様に分岐します。

ただし、すべての経路が完全に逐次化されるわけではありません。`fused_gr_read_multi` は複数 token の fused 経路を保ち、この変数を使って kernel の token 数特殊化を選ばないようにします。

## 値と判定

読み取り側は `getenv()` の結果を、未設定か、空文字か、先頭文字が `0` かで判定します。文字列全体や数値としての妥当性は調べません。

| 値 | 判定 |
|---|---|
| 未設定 | OFF |
| 空文字 | OFF |
| 先頭文字が `0`（例: `0`, `0abc`） | OFF |
| その他の非空文字列（例: `1`, `2`, `true`, `false`, `-1`, ` 1`） | ON |

CUDA/SYCL の GR kernel と MTP には同じ判定式が複数あります。Verifier は `env_on()` を使い、同じく「未設定でなく、空でなく、先頭文字が `0` でない」場合に ON とします（`src/core/verify.cpp:172-182`, `sycl/src/core/verify.cpp:92-104`）。

## 有効になる条件

- 通常の GR の multi-token 読み書きへの影響は、`gr_read_multi` / `gr_write_multi` が呼ばれ、`native_mmvf` が有効で、対象 token 数が 1 より大きい場合に現れます。この条件で OFF なら native multi-token 経路を使い、ON なら token ごとの関数呼び出しに進みます（`src/kernels/cuda/gr.cu:422-457,479-497`; SYCL 対応実装: `sycl/src/kernels/cuda/gr.dp.cpp:696-702,786-800`）。
- Verifier の residual write は `dec_batch` が有効で、複数行を処理するときだけ multi-write の選択が関係します。`STRATA_NO_MULTI_GR` が ON なら各 token の `gr_write()` を呼びます（`src/core/verify.cpp:1011-1032,1676-1680`; SYCL: `sycl/src/core/verify.cpp:956-962,1520-1524`）。
- MTP の residual write は `fuse_head_gr` が無効な場合に分岐します。ON ならループ内で token ごとの `gr_write()`、OFF ならループ後に `gr_write_multi()` を使います。`fuse_head_gr` が有効な場合はこの分岐を通らず、fused 経路を使います（`src/core/mtp.cpp:924-943,945-957`; SYCL: `sycl/src/core/mtp.cpp:1072-1091,1093-1105`）。
- fused CUDA GR kernel では ON の場合 `exact_t` を無効にし、`gr_down_staged_kernel` の token 数ごとの `<1..6, true>` 特殊化を選ばず、汎用 kernel 分岐へ進みます。また `gr_up` 側は実 token 数でなく `kFusedGrMaxT` を使った switch になります。ここでも複数 token をまとめる fused 呼び出し自体は残ります（`src/kernels/cuda/fused_gr.cu:1052-1082,1097-1117`）。

## 実行時の詳細

Verifier 側の値は `verify.cpp` のグローバル `const bool` 初期化時に読み取られます。GR kernel と MTP の関数内にある値は、それぞれの static 初回評価時に保存されます。いずれも一度評価した後は環境を書き換えても同じプロセスでは反映されません。起動時に設定して使います。

この変数を読んで値に応じた専用ログを出す箇所は、調査対象ソースでは確認できませんでした。変更するのは GR/MTP の処理経路と kernel の選択です。`docs/DETAILS.md` には CPU の IQ multi-token kernel と丸め差に関する説明がありますが、`STRATA_NO_MULTI_GR` の説明や、この変数による GR の数値同一性・性能測定は見つかりませんでした（`docs/DETAILS.md:97-105`）。そのため、この資料から GR 側の出力同一性や速度効果は断定しません。

## 根拠

- 共通の値判定と Verifier の multi-write 分岐: `src/core/verify.cpp:172-182,1011-1032,1676-1680`; SYCL: `sycl/src/core/verify.cpp:92-104,956-962,1520-1524`。
- CUDA の multi-token GR read/write の切替: `src/kernels/cuda/gr.cu:414-457,479-497`; SYCL: `sycl/src/kernels/cuda/gr.dp.cpp:688-702,786-800`。
- MTP の値判定と residual write: `src/core/mtp.cpp:924-943`; SYCL: `sycl/src/core/mtp.cpp:1072-1091`。
- Fused CUDA GR kernel の token 数特殊化: `src/kernels/cuda/fused_gr.cu:1052-1082,1097-1117`。
- 関連する資料の範囲: `docs/DETAILS.md:97-105`。
