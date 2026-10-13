# `STRATA_SPLIT_SMALL_OWN`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

層分割した `strata serve` で、後段 GPU など各 stage が自身の expert cache の末尾に prompt path 用の領域を確保し、短い prompt ではその領域だけを使うための設定です。`S` は確保領域を見積もる prompt chunk の token 数です。各 stage の対象領域にいた expert は起動時に非 resident 扱いとなり、device residency table に反映されます。長い prompt では確保領域より手前の cache slot を追加で借りられます。

これは起動時に一度読む serve 経路の設定です。通常の単一 GPU 実行には適用されません。

## 値と判定

値は文字列全体の検証ではなく `std::atoll` で符号付き整数に変換し、その結果を `request_chunk()` に渡します。`request_chunk()` は token 数が 0 以下、または chunk 上限が 0 以下なら 0 を返し、それ以外は 256 の倍数へ切り上げて `--prefill` の chunk 上限で制限します。

| 設定 | 結果 |
|---|---|
| 未設定 | `S=0`。機能を無効化 |
| 空文字、数値に変換できない文字列 | `atoll` の結果は 0 となり、機能を無効化 |
| 正の整数 | 256 token 単位に切り上げ、`o.prefill_chunk` 以下に制限した値が `S` |
| 0 または負数 | `request_chunk()` が 0 を返し、機能を無効化 |
| 数字の後ろに文字がある値 | `atoll` が先頭の整数部分を変換し、その後ろは判定に使わない |

たとえば `257` は通常 `512` token の `S` になりますが、`--prefill` 上限がそれより小さければその上限になります。大きすぎて `atoll` の変換範囲を超える値について、呼び出し側にエラー検査や fallback はありません。

有効な `S` のとき、関連設定 `STRATA_SPLIT_SMALL_MAX=M` が未設定なら上限は `S` です。設定されていれば同じく `atoll` で読み、実際の上限を `max(S, M)` とします。したがって M が空、非数値、0、負数、または S 未満でも上限は少なくとも S です。この関連変数の説明全体は本書の対象外です。

## 有効になる条件

- serve 起動で `multi_gpu` が真である（複数 GPU の層分割）。
- prompt 用 stage cache のリスト `pf_parts` が空でなく、resident table `host_res` が存在する。
- 変換後の `S` が正で、対象 stage の `p.first` が有効である。

条件を満たさない場合、値が設定されていても予約・resident table の変更はありません。環境変数を CLI 引数や設定ファイルが上書きする経路はなく、`S` の最大値に `o.prefill_chunk` が使われます。

## 実行時の詳細

serve エンジンの初期化時、条件を満たす場合に `STRATA_SPLIT_SMALL_OWN` を読みます。各借用対象 stage について `part_slots(p, S)` で S-token chunk の prompt buffers に要る slot 数を求め、`first_s = max(p.first, cache_slots - part_slots(p, S))` とします。その stage が担当する layer の expert のうち、resident slot 番号が `first_s` 以上のものを `kNotResident` に変更します。該当 expert 数を stderr に `strata serve:   CUDA%d keeps ... slots for ...-token prompts (... experts no longer resident)` と出し、1個以上変更した場合は primary と各 stage の device residency table を更新します。SYCL 側のコピーも同じログ文字列を持ちます。

prompt segment を貸し出す際、`tokens <= split_small_max` なら通常の必要 chunk `want_full` を `min(want_full, S)` にし、stage ごとにその chunk の buffers に必要な slot だけを借ります。初期化時に S-token 分を予約しているため、この範囲の prompt では当該予約領域を越える expert slot の貸し出し・refill は不要です。`tokens > split_small_max` では通常の `want_full` を使い、必要な範囲を借ります。空の segment など通常の lend 条件によるエラー処理は別途あります。

slot を非 resident にすると、GPU residency table から expert が外れます。関連する serve 実装はその slot を「貸し出し」対象として扱い、prompt path 用 buffer に置き換えます。したがってこの設定は cache residency と prompt の slot 使用を変えるもので、単なるログ設定ではありません。ソースだけでは、この変数を使った場合の出力同一性や性能値を保証できません。

## 根拠

- `src/program/generate.cpp:6326-6332` — `request_chunk()` の切り上げ・上限処理。
- `src/program/generate.cpp:7389-7424` — 変数読み取り、関連上限、stage ごとの予約計算、resident table の変更とログ。
- `src/program/generate.cpp:7017-7019,10903-10907,10927-10960` — slot 数計算と prompt segment ごとの chunk 選択・slot lend。
- `sycl/src/program/generate.cpp:5973-5979,6962-6997,10148-10154` — SYCL コピーの同等処理。
- `docs/MULTI_GPU.md:76-83` — #340 の層分割・短い prompt の一般的背景を説明。ただし同節で記載される設定名は `STRATA_SPLIT_OWN` であり、本変数の効果や測定値を直接説明する資料ではありません。
