# `DS4_PROF`

調査対象: Strata `main` の HEAD `4b9e05a2a806a3fe24f7b2560d98626c37dade35`（2026-10-26 時点）。外部ライブラリの環境変数は対象外。

## 役割

DeepSeek V4.1（DS4）モデルの CUDA 実行に、GPU CUDA event によるステージ別時間計測と診断ログを加えます。decode window、chunk 化 prompt、特定の CPU expert 経路の計測を有効にします。環境変数は処理選択や計算値を変更する分岐には使われず、時間計測と stderr 出力を制御します。

## 値と判定

| 環境変数の状態 | 判定 |
|---|---|
| unset | 無効 |
| 値あり（空文字を含む） | 有効 |

`std::getenv(...) != nullptr` の有無だけを見ます。`1` との比較、数値変換、空文字検査はありません。したがって `DS4_PROF=0` や `DS4_PROF=false` も有効です。

## 有効になる条件

- DS4 の CUDA 実装（`src/dsv41/ds4_model.cu`）を使う実行経路が対象です。この調査では他 backend に同名変数の読み取り実装を確認していません。
- prompt の chunk 実行では、有効値が `prof_chunk` に反映され、実行後に prompt 全体の GPU 時間と詳細表を出力します。
- window 実行では `T == 1` のときにだけ decode 計測を記録します。複数 token の window は decode の `prof_window` 計測対象外です。
- CPU 側では IQ rows の expert 経路を通った場合にだけ別の CPU lane 集計が動きます。

## 実行時の詳細

GPU / prompt 計測用の `prof_on` は `Impl` の初期化時に読み取られ、そのインスタンス内の prompt・decode 計測に使われます。環境値をモデル実行中に変更しても、この値は更新されません。chunk 実行では層のイベントを記録し、実行完了時に各 device の stream を同期してからイベント間の時間を集計します。stderr には `ds4 prompt GPU time, ...` と `ds4 prof ...` の行が出ます。計測区間は複数 device の値を合算し、prompt の各ステージの合計時間・割合や expert kernel の内訳を表示します。

`T == 1` の window 実行では、GPU event のステージ時間を `Stats::prof_ms` に加算します。`ds4_main.cpp` は prompt 後の stats を基準値として取り、生成後に profiled token が増えていれば `GPU per token (DS4_PROF): ...` を stderr に出します。表示項目は層間、attention、routing + shared expert、experts gate/up、CPU lane 待ち、down + post の各 ms/token です。従って生成 token がない場合や、計測対象の window がなければこの行は出ません。

CPU IQ rows 経路の `static const bool on` は、最初にその経路へ入った時に値を読み、その後プロセス内で保持します。有効時は各呼び出しの CPU 時間を集計し、1000 call ごとに stderr へ `ds4 prof CPU lane (IQ rows) per call: ...` を出します。この静的判定は `Impl` の `prof_on` とは別に評価されます。

## 根拠

- `src/dsv41/ds4_model.cu:1146-1149` — GPU 計測フラグを環境変数の設定有無で初期化。
- `src/dsv41/ds4_model.cu:1194-1229` — device stream 上の event 記録、集計、token 数の更新。
- `src/dsv41/ds4_model.cu:8261,8325-8343,8382-8383` — chunk prompt の計測有効化、同期、ログ、集計リセット。
- `src/dsv41/ds4_model.cu:8611,8627` — 1 token window のみ有効化し、window 後に集計。
- `src/dsv41/ds4_model.cu:5809-5817` — CPU IQ rows 経路の独立した static 判定、1000 call ごとのログ。
- `src/dsv41/ds4_model.hpp:83-84` — decode 用の集計値。
- `src/dsv41/ds4_main.cpp:1382,1443-1453,1503-1511` — prompt 後の基準値、生成後の profiled token 判定と ms/token ログ。
- `docs/DETAILS.md` および `docs/` の検索では `DS4_PROF` の説明を確認できませんでした。
