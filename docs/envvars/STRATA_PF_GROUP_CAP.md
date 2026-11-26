# `STRATA_PF_GROUP_CAP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`STRATA_PF_GROUP_CAP` は、prompt の MoE MMQ 処理で `STRATA_PF_GROUP_SCRATCH` が有効な場合に、1 グループ分の GU/H/Hq scratch が保持する最大 row 数を指定する内部テスト用 knob である。正の値は chunk の token 数 `T` より小さくならないよう補正され、グループの合計 row 数が上限を超える場合、そのグループの expert を複数の sub-range に分けて gate/up、SwiGLU、量子化、down を実行する。未設定または正でない値では、`T` とグループ平均から計算した自動上限を使う。単独では scratch 機能を有効にしない（`engine/src/prefill/prefill.cpp:2209-2216, 2233-2239, 6506-6522, 7310-7351`）。

対象名の全参照を調べた結果、実際の環境読み取りは `engine/src/prefill/prefill.cpp:2236` の一箇所だけだった。`terminal/data/settings-register.json:31230-31244` にも名前と `int` の分類があるが、これは環境値の読み取りではない。Strata のソースでは CLI 引数、設定ファイル、別環境変数からこの値を設定・転送する箇所は見つからなかった。

## 値と判定

`group_cap_rows()` 内の関数ローカル `static const int64_t forced` 初期化で `std::getenv` を一度呼び、設定されていれば `std::atoll` で整数変換する。文字列全体の検証はなく、数値として読める先頭部分を使う。空文字や数値で始まらない文字列は 0 相当となり、自動上限へ進む。小数点や後続文字も検査されない。変換後が正なら `max(forced, T)`、0 以下なら自動計算である（`engine/src/prefill/prefill.cpp:2233-2239`）。

| 入力 | 判定 |
|---|---|
| 未設定 | `forced=0`。自動上限を使用 |
| 空文字、`0`、`-1`、`true`、`false`、`0anything` | 変換結果は正でないため自動上限を使用 |
| `1`、`+12`、`12rows`、`12.5` | 先頭の整数部分を読み、正の値として扱う。ただし上限は少なくとも `T` |
| 整数として読めない値、範囲外の値 | 明示的なエラー・範囲検査・fallback はない。範囲外変換の結果はこのコードから保証できない |

自動上限は `avg = T * K * MMQ_GROUP / max(n_expert, 1)` として計算し、`T + 3 * avg` を 64 row 単位に切り上げる。`T` は chunk の token 数、`n_expert` は expert 数である（同ファイル `:2238-2239`）。

## 有効になる条件

- `STRATA_PF_GROUP_SCRATCH` も有効であること。そちらは `getenv` の設定有無ではなく `atoi(value) != 0` で判定するため、空文字や `0` は無効。未設定なら `STRATA_PF_GROUP_CAP` の値を使わない（`engine/src/prefill/prefill.cpp:2215-2217, 2234-2237`）。
- prompt の MMQ plan が少なくとも一層で MMQ を使い、FP16 / `pf_wmma` fallback がなく、すべての層が MMQ を使い、`STRATA_MMQ_DIRECT` の direct 経路を使う層がないこと。条件を満たさないと `STRATA_PF_GROUP_SCRATCH` は無視され、理由を stderr に出す。この場合 `group_cap_rows()` に到達せず、この変数は読み取られない（同ファイル `:2219-2229`）。
- `STRATA_PREFILL_MMQ=0` などで MMQ が無効なら適用されない。`STRATA_PF_WMMA` が CUDA GPU 条件を満たして使われる場合も scratch は適用されない（同ファイル `:1970-1986, 2026-2037, 2219-2229`）。
- 別の層・chunk で実行時に fused または FP16 path が選ばれた場合は、prefill が失敗する保護分岐がある（同ファイル `:5707-5710`）。
- 候補名の読み取りは CUDA/HIP で使われる `engine/src/prefill/prefill.cpp` にある。SYCL 側の別実装には参照がない。同じ共通ファイルは Metal の CMake にも含まれるが、Metal build でこの MMQ scratch 条件が成立するかはこのソース調査だけでは確認できない。cap が適用されるには、いずれの build でも上記 MMQ と scratch の条件を通る必要がある。

## 実行時の詳細

`STRATA_PF_GROUP_SCRATCH` が適用される sizing で `moe_bufs()` が呼ばれると cap が計算され、GU/H/Hq の確保量と bounds table の容量に反映される。`Prefill::init` は `m.group_cap` に chunk ごとの上限を保存する（`engine/src/prefill/prefill.cpp:2333-2338, 2571-2575, 2845-2851, 2912-2918`）。

値の `getenv` 読み取りは `group_cap_rows()` の static 初期化時のみで、以後プロセス内でキャッシュされる。環境値を変更してもそのプロセスには反映されない。環境変数を子プロセスへ設定・上書きする Strata 側の処理は見つからなかった。

各 MMQ グループの row 数が `m.group_cap` 以下なら通常の一グループ処理を使う。超えると expert 境界に沿って sub-range を構成し、各 range の row 数を上限以下にして処理する。単一 expert の row 数は chunk の最大 `T` row なので、指定上限も最低 `T` に丸める。range が上限を超える場合は `prefill: STRATA_PF_GROUP_SCRATCH: a range of ... rows passes the scratch's ...` をエラーとして返す。bounds table が割り当て容量を超えた場合も `prefill: STRATA_PF_GROUP_SCRATCH's bounds table overflowed` で失敗する（同ファイル `:6506-6527, 7310-7355`）。

## ログと測定値

cap 専用のログはない。scratch が有効な layout の初期化時には stderr に `strata prefill: chunk <T> tokens: STRATA_PF_GROUP_SCRATCH on (GU/H/Hq hold <cap> rows, not <T*K>);` と出て、採用された row 上限を確認できる（`engine/src/prefill/prefill.cpp:2912-2918`）。無効条件では `strata prefill: STRATA_PF_GROUP_SCRATCH=1 is ignored: <理由>` を出す（同ファイル `:2218-2227`）。エラー経路は「実行時の詳細」に記した。

`docs/DETAILS.md:1278` は `STRATA_PF_GROUP_SCRATCH` と `STRATA_PF_HC_REGION` の効果・測定値を記述しているが、`STRATA_PF_GROUP_CAP` の値を変えた測定値や性能保証は示していない。この文書でも cap による速度・精度の変化は断定しない。

## 根拠

- `engine/src/prefill/prefill.cpp:2215-2245` — scratch の適用判定、自動・強制 cap、bounds 容量。
- `engine/src/prefill/prefill.cpp:2333-2338, 2571-2575, 2845-2851, 2912-2918` — buffer sizing と layout への適用、ログ。
- `engine/src/prefill/prefill.cpp:6506-6527, 7310-7355` — sub-range 生成、処理、失敗経路。
- `engine/src/prefill/prefill.cpp:1970-1986, 2026-2037, 5707-5710` — backend/plan 条件と runtime guard。
- `docs/DETAILS.md:1278` — 関連する group scratch の資料。cap 固有の説明・測定値はない。
