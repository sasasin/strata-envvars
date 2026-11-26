# `STRATA_PCIE_BALANCE`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA verifier が layer ごとに PCIe へ回す expert miss 数を、固定 share から CPU pool と GPU の計測コストに基づく選択へ切り替える opt-in 変数。通常の PCIe share は `pcie_frac` から得た件数だが、この機能を有効にすると、測定モデルが準備できた後は各 layer の miss のうち CPU と GPU の予測時間の最大値を小さくする件数を選ぶ。対象は転送・計算の割り振りであり、ルーターの expert 選択自体を変更する処理ではない（`engine/src/program/generate.cpp:5590-5597`、`engine/include/strata/core/expert_source.hpp:496-509`）。

生成とサーバーのどちらも verifier の初期化前に同じ有効判定を行い、条件を満たす場合は `drive.d.pcie_model` を verifier に渡す（`engine/src/program/generate.cpp:13489-13491`, `24491-24504`）。

## 値と判定

`std::getenv` の戻り値を `std::strcmp(e, "1") == 0` で文字列全体比較する。unset は無効、空文字も無効で、文字列が正確に `1` の場合だけ有効。数値変換はせず、空白除去・大文字小文字変換・先頭文字だけの判定もない（`engine/src/program/generate.cpp:5594-5597`）。

| 条件 | unset | 有効になる値（例） | 無効になる値（例） |
|---|---|---|---|
| 共通の有効判定 | 無効 | `1` | 空文字、`0`、`true`、`01`、`1 `、` 1`、`0anything` |

## 有効になる条件

- CUDA の単一 GPU verifier であること。layer split 等の複数 GPU 経路では `multi_gpu` が真となり無効。サーバーではさらに `n_stages == 1` の場合だけ verifier に設定する（`engine/src/program/generate.cpp:4856`, `5594-5597`, `13489-13491`, `24499`）。
- native expert pack であること（`native_pack` が真）。canonical pack では環境変数が `1` でも無効（`engine/src/program/generate.cpp:5445`, `5594-5597`）。
- `o.batch <= 0` であること。`--batch`（別名 `--slots`）で正の batch 数を指定した経路では有効にならない（`engine/src/program/generate.cpp:4041-4042`, `5594-5597`）。
- 起動時の `--pcie-frac` が有効指定として認識されないこと。`pcie_given` は解析後の値が `>= 0.0` かで決まり、明示した `0` も変数を抑止する。引数は `std::atof` で解析されるため、数値でない文字列は `0` となり、この判定では指定ありになる。負の値はこの判定上は未指定扱い（`engine/src/program/generate.cpp:4057`, `4780-4782`, `5594-5597`）。
- サーバーでは要求ごとの `pcie_frac` 指定が優先され、その要求中はモデル計測を pause する。要求に `pcie_frac` がなければ計測・モデル利用を続ける（`engine/src/program/generate.cpp:18859-18870`, `18922`, `21441-21446`; `engine/include/strata/core/verify.hpp:448-452`）。
- 有効化直後はモデルが計測値を十分に得るまで固定 share を使う。`PcieModel::ready()` は CPU fit に8件以上、PCIe expert を含む GPU fit に4件以上の計測があることを要求する。計測できない layer や全 expert が VRAM resident の window ではモデル更新されない（`engine/include/strata/core/expert_source.hpp:461-495`; `engine/src/core/verify.cpp:4173-4180`, `4325-4337`）。

## 実行時の詳細

環境変数の判定は `pcie_balance` lambda が呼ばれたときに行い、`static` cache はない。ただし実際の呼び出しは生成またはサーバーの verifier 初期化時だけで、その verifier にモデル pointer を設定する。そのためプロセス起動後に環境を変更しても既存 verifier には反映されない（`engine/src/program/generate.cpp:5594-5597`, `13489-13491`, `24491-24504`）。

モデルが有効で miss がある layer では、CPU pool と GPU の処理時間を verify window ごとに採取して fit を更新する（`engine/src/core/verify.cpp:4173-4180`, `4325-4337`; `engine/include/strata/core/expert_source.hpp:441-495`）。fit が ready になると、各 layer の `nmiss` 件について PCIe に回す数 `k` を `0..nmiss` で比較し、予測された CPU と GPU の時間の最大値を最小にする `k` を採用する。ready 前、またはモデルが off の間は固定 share 由来の件数を使い、モデル on の間は64回に1回、全件が同じ側に寄る割当を避けるため1件を反対側へ移す探索も行う（`engine/include/strata/core/expert_source.hpp:496-509`）。

dispatch 側では VRAM hit、peer/helper 側などを除いた miss 数を数え、その layer が PCIe 対応である場合に `PcieModel::pick` を呼ぶ。選ばれた件数は routing 順の miss から PCIe fetch 対象になり、実際には pinned blob があり staging 容量内のものだけが転送される（`engine/src/core/expert_source.cpp:5491-5500`, `5543-5545`, `5593-5607`）。

モデル用の CUDA mapped stamps 確保に失敗すると verifier 初期化が失敗し、呼び出し元は `strata generate: <error>` または `strata serve: <error>` を出して終了コード `1` を返す（`engine/src/core/verify.cpp:1142-1151`; `engine/src/program/generate.cpp:13496-13501`, `24503-24505`）。

## ログと測定値

生成経路では、round が1回以上あり balance verifier が設定済みなら、標準出力に `pcie model` として `CPU ... us + ... an expert + ... a PCIe one, GPU ... us + ... a PCIe expert (the PCIe count per layer from these)` を出す。これはモデルの fit 係数であり、変数が無効、round がない、または適用外の条件ではこの行は出ない（`engine/src/program/generate.cpp:25360-25365`）。有効化だけを知らせる専用の警告・終了ログは確認できない。

`docs/DETAILS.md:1264,1721` は RTX A4000 arena で +5.6%、RTX 3060 resident で -1.6%、Tesla P100 で -1.3% を記録し、同資料 `docs/DETAILS.md:1496` は single card では遅いと記載する。測定行にある条件は IQ3_XXS、5 pairs で、ここに記載された範囲を超える一般的な性能効果は示さない。これらは資料上の測定記録であり、本調査で再測定していない。

## 根拠

- `engine/src/program/generate.cpp:5590-5597` — 変数の唯一の実読み取り、完全一致判定と適用 gate。
- `engine/src/program/generate.cpp:13489-13491`, `24491-24504` — serve / generate の verifier への設定。
- `engine/include/strata/core/expert_source.hpp:423-428`, `441-509` — fit の説明、ready 条件、件数選択。
- `engine/src/core/verify.cpp:1142-1151`, `4173-4180`, `4325-4337` — stamp 確保、window 後の測定・fit 更新。
- `engine/src/core/expert_source.cpp:5491-5500`, `5543-5545`, `5593-5607` — miss 数と PCIe 件数の適用、fetch 条件。
- `engine/src/program/generate.cpp:18859-18870`, `18922`, `21441-21446` — server request の share 指定と pause。
- `engine/src/program/generate.cpp:25360-25365` — generate の fit 出力。
- `docs/DETAILS.md:1264`, `1496`, `1712-1721` — 文書化された適用範囲・測定記録。
