# `STRATA_KVA_DRAFT_FLOOR`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。外部ライブラリの環境変数は対象外。

## 役割

KVA が近似した prompt 区間から作られる MTP draft layer の K/V cell を、draft attention で読まず、prompt prefill 時にも作らないための研究用スイッチです。通常の target model の計算や KVA 自体を有効にはしません。floor は KVA がその session で近似した範囲の先頭実セル位置で、draft layer の既存 attention window の開始位置をそれより前に戻さないようにします。MTP は target model の代わりではなく、draft token は引き続き target 側で検証されます（`include/strata/prefill/kva.hpp:26-32,98-102`; `include/strata/core/mtp.hpp:175-191`）。

## 値と判定

設定値は `kva_env_flag()` が読み、値を数値や boolean 文字列として parse せず、先頭文字だけ比較します（`include/strata/prefill/kva.hpp:143-147,161`）。

| 環境値 | `draft_floor` | 判定 |
|---|---:|---|
| unset | false | helper の既定値 `false` |
| 空文字 | false | `v[0] == '\0'` のため既定値 |
| `0`、`0abc` | false | 先頭文字が `0` |
| `1`、`true`、`2`、`false`、空白で始まる値など | true | 空文字でなく、先頭文字が `0` 以外 |

したがって `false` は無効を意味せず有効になります。後続文字列、大文字小文字、数値としての妥当性は検査されません。clamp や範囲指定はこの環境値にはありません。CLI 引数からこの flag を上書きする実装はありません。

## 有効になる条件

`draft_floor` を true にしただけでは作用しません。`wants_cell_floor()` は、KVA backend があること、`STRATA_KVA` により KVA が on であること、KVA が engine 全体について block されていないこと、draft floor flag が true であること、MTP drafter があることをすべて要求します（`include/strata/prefill/kva.hpp:43-49,98-102`; `src/program/generate.cpp:6263-6279`）。Metal では `kKvaBackend` が false です。`STRATA_KVA=0` または未設定なら floor flag だけ設定しても無効です。

MTP drafter の条件は `--mtp` が指定され `--spec` が 2 以上であることです。これを満たさない場合 `enable_cell_floor()` は有効化されません。MTP が無い、または `--spec` 不足で `--mtp` が無視された場合も floor は働きません（`src/program/generate.cpp:6278-6286,6298`）。

さらに、その prompt read で実際に KVA 近似が成立した範囲がなければ floor は 0 のままです。KVA 自体は cold read（`pos0 == 0`）、全 trunk、画像なし、DFlash2 taps なし、最小 prompt 長以上で tail を越える長さなどを要求し、batch slots、layer split、peer device は engine 全体で KVA を block します。モデル shape は既定で測定対象に限られ、`STRATA_KVA_ANY_MODEL` が override します（`include/strata/prefill/kva.hpp:104-133`; `src/program/generate.cpp:6269-6278`）。この文書の flag はそれらの KVA 条件を緩和しません。

## 実行時の詳細

Production path は `kva_config()` の function-local `static const KvaConfig` を通じて設定を初回取得時に読み、プロセス内に cache します。以降の環境値変更は反映されません（`include/strata/prefill/kva.hpp:149-161,191-195`）。`STRATA_KVA_DRAFT_FLOOR` は起動時の KVA config 作成時に他の KVA 設定と一緒に評価されます。

floor が有効なら、generate 初期化時に MTP drafter の load より前に `enable_cell_floor(true)` が呼ばれます。mapped floor buffer の確保に失敗すると load は `mtp: the window floor does not fit` を返し、generate は `strata generate: ...` を stderr に出して終了コード 1 で戻ります（`src/program/generate.cpp:6278,6293-6298`; `src/core/mtp.cpp:406-409`）。

KVA prompt の各 chunk で floor が上がった場合、draft K/V prefill は `first_needed()` より前の row を処理対象から外します。decode 側は mapped floor を参照し、通常の window 開始位置と floor の大きい方から draft attention の cell を選びます。floor が `n_kv` の末尾以降でも、cell があるときは少なくとも最後の 1 cell を残します（`src/program/generate.cpp:11000-11005,15247-15252,17768-17779`; `src/prefill/prefill.cpp:1960-1963`; `src/core/mtp.cpp:1074-1076`; `src/kernels/cuda/verify_kernels.cu:1022-1042`; `include/strata/kernels/window_start.hpp:17-23`）。

floor は process 全体の固定値ではなく、prompt token prefix に対応づけて session の続きに適用されます。新規 request は 0 から始め、KVA が実際に近似したときに floor を登録します。既存 session からの続行では token prefix の一致範囲を検索し、checkpoint reread のように先頭から読み直す場合や一致する KVA state がない場合は 0 を設定します（`src/program/generate.cpp:10390-10392,14733-14738,15249-15252`; `include/strata/prefill/kva_floor.hpp:23-56`）。

## ログと根拠

通常の floor 有効化・適用を示す専用ログは見当たりません。KVA 自体の適用／不適用ログは `STRATA_KVA` の制御についてであり、draft floor の有効性を示すものではありません（`src/prefill/prefill.cpp:5820-5856`）。確認できる明示的な失敗経路は上記の mapped floor buffer 確保失敗です。

設計資料 `docs/KVA.md:64-77,110-115` も、既定 off の研究用設定であり、近似区間から作った draft cell を避ける説明です。挙動の判定根拠は候補一覧やテストではなく、上記の実装箇所です。
