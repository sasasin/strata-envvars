# `FNX_PF_DRAFT8`

調査対象: Strata `main` の HEAD `ffa80d73133ea5c548aefe57889a16e8085a938f`（2026-11-03 時点）。

## 役割

`strata-split-N` の prompt prefill で、MTP draft layer の prompt 状態を準備する順序を切り替えます。既定（unset / 0）では各 chunk の main layer 計算に続けて `prefill_draft()` を呼び、draft layer の K/V と QSA key を作ります。有効時（非ゼロ整数）はこの処理を main prefill pass の同期後まで遅らせ、main layer の残差行と次 token を `draft_rows()` に渡して MAXT 行ずつ処理します。これは draft layer を有効にするスイッチではなく、MTP が接続されている場合の prompt 経路の切り替えです。

対象コードは sFNX split engine です。ビルド設定上、この実行ファイルは opt-in の `STRATA_BUILD_SPLIT=ON` で作られ、Linux CUDA または Linux HIP のみを対象にします。通常の Strata engine や他の split 外 backend でこの変数を読む箇所は見つかりません（`src/split/CMakeLists.txt:1-7,20-30,64-80,92-103`）。

## 値と判定

`env_flag()` は `env_int(name, 0) != 0` です。値が設定されているかではなく、符号付き十進整数として全体を parse した結果で判定します。

| 環境値 | 結果 |
|---|---|
| unset | 0（無効） |
| `0`, `+0`, `-0` | 無効 |
| 任意の非ゼロ整数（負数を含む） | 有効 |
| 空文字、空白、`true` / `false`、数字の後ろに文字がある値、小数、整数範囲外 | `std::runtime_error`。切替は行われない |

整数 parser は任意符号と数字のみを許し、`strtoll` で `long long` に変換し、文字列末尾まで消費したことと overflow がないことを検査します。空文字は整数として不正です（`src/split/src/env.hpp:15-22,33-52`）。CLI 引数、設定ファイル、他の環境変数による上書きや優先順位はありません。

## 有効になる条件

- 読み取り箇所は `Engine::prefill_pass()` 内で、CUDA/HIP 共通の `src/split/src/prefill.cu` にあります。CMake は同じソースを CUDA または HIP 言語として split engine に含めます（`src/split/src/prefill.cu:1310`; `src/split/CMakeLists.txt:64-80,92-103`）。
- 値が非ゼロでも、実際の draft 処理は `mtp_` が接続されている場合だけです。`mtp_` が null なら両方の `if (mtp_ && ...)` を通らず、この変数による処理差はありません（`src/split/src/prefill.cu:1311-1316,1337-1349`; MTP の設定は `src/split/src/engine.cu:1175-1178`）。
- 変数に対応する追加の OS、GPU 世代、build macro、CLI フラグ条件はありません。ビルドそのものが split engine の Linux CUDA/HIP 条件を満たす必要があります。

## 実行時の詳細

各 chunk では main layer の最終 residual `p.R` を作り、次 token を組み合わせて draft 状態を準備します。既定経路の `prefill_draft()` は draft layer の embedding / hidden 処理、QSA index、K/V append までを実行し、prompt 上の draft layer 出力は参照しないと実装コメントにあります（`src/split/src/prefill.cu:944-978,1311-1316`）。

非ゼロ経路は main prefill stream が完了し ring error がないことを確認した後、各 chunk を MAXT 以下の行群に分けます。各行群について、入力 token の次 token 列（chunk 内の次 token と末尾の `after` を含む）と `p.R` の行を渡し、`draft_rows()` で draft graph を実行します（`src/split/src/prefill.cu:1317-1349`）。`draft_rows()` は MTP を必要とし、文脈範囲と行数を検査し、draft embedding を作って graph を起動して stream を同期します。したがってこの経路では prompt 状態の準備だけでなく、`draft_rows()` が実装する draft 推論処理も呼ばれます（`src/split/src/engine_common.cu:1381-1392,1412-1438,1456-1467`）。

環境値は関数内の `static const bool` に初回評価結果が保存されるため、プロセスの最初の `prefill_pass()` で読み、一度確定すると同一プロセス内で後から環境を変更しても再評価されません（`src/split/src/prefill.cu:1038,1310`）。unset の既定は無効です。特別なログはありません。`FNX_PF_TIMING` も有効なら pass の `draft layer` 所要時間が stderr に出ますが、この値単独では出力されません（`src/split/src/prefill.cu:1353-1364`）。

不正値は `env_int()` の例外として prefill 呼び出し元へ伝播します。sFNX server の `srv.run()` 中に捕捉された例外は `ERR <理由>` を出力し、stderr に `sfnx: failed: <理由>` を記録して終了コード 1 で終了します（`src/split/tools/sfnx.cpp:1030-1035,1086-1089`）。エラー文は helper 由来の `FNX_PF_DRAFT8: '<値>' is not a whole number` です（`src/split/src/env.hpp:33-39`）。

## 根拠

- 名前の全参照検索では実装参照は `src/split/src/prefill.cu:1310` のみでした。候補一覧 `docs/envvars/000_envvers.md:562` には掲載されています。
- `docs/DETAILS.md` と `docs/SPLIT_SERVE.md` にこの変数固有の説明は見当たらず、性能差や生成結果への影響はこの調査では確認していません。
