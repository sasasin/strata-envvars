# `STRATA_PREFILL_TIMING`

調査対象: Strata `main` の HEAD `296b59d2f73c8f04a805df29c2fa97655adace78`（2026-10-14 時点）。

## 役割

バッチ prompt prefill の処理時間をフェーズ別に stderr へ出す診断用スイッチです。通常の CUDA/HIP 実装と、別ビルドの実験的 SYCL 実装の両方に同名の読み取りがあります。`strata` の生成・サーバー処理で prefill の `run_impl()` が実行されると使われます。Metal prefill は別経路で `run_impl()` より前に戻るため、この計測処理を通りません。

## 値と判定

| 値 | 動作 |
|---|---|
| 未設定 | 計測しない。既定 OFF。 |
| 設定済み（空文字を含む） | 計測する。値の内容は読まない。 |

判定は `getenv(...) != nullptr` のみです。`=0`、`=false`、空文字も有効で、数値変換・文字列比較・範囲制限はありません。CLI や設定ファイルによる上書きはありません。`PfTimer` と `PeTimer` の構築時にそれぞれ読み取るため、実行中の変更は既存 timer に反映されず、次の `run_impl()` 呼び出しでは再評価されます。

## 有効になる条件

- CUDA/HIP ビルドでは `src/prefill/prefill.cpp` の計測コードが使われます。CMake の `strata_prefill` ターゲットがこのソースを含み、HIP でも同じターゲットを使用します。
- SYCL は CUDA/HIP と同時ではない独立した実験的ビルドで、`sycl/src/prefill/prefill.cpp` に対応する計測があります。
- prompt がバッチ prefill の実装を通る必要があります。backend・処理経路がこの `run_impl()` を使わない場合は出力されません。
- peer GPU がある場合は peer stream の計測も作られます。peer がない場合、peer timer は無効にされます。

## 実行時の詳細

CUDA/HIP では compute stream 上に CUDA event を順番に記録し、連続する event 間の時間を先に記録したフェーズへ加算します。ホストによる expert grouping や expert copy を GPU が待つ区間も、その時点で記録中のフェーズに含まれます。MoE layer ごとの同期後に event 区間を集計して再利用し、prefill 終了時に残りを集計します。フェーズ名には `embed+steps`、`hc read`、`gdn`、`qsa proj`、`qsa indexer`、`qsa select`、`qsa attn`、`router+shared`、`host grouping`、`gather`、`wait copy`、`dequant`、`gemm gate/up`、`gemm down`、`combine`、`ple`、`kv stage`、`gdn conv+gates`、`gdn recurrence`、`gdn out proj` があります。

SYCL でも queue 上の event 区間を集計します。加えて `pt.on` のとき、chunk setup の内訳を出すために setup 中の queue を `wait()` する箇所があります。このため SYCL では診断出力だけでなく同期のタイミングも変わり得ます。CUDA/HIP でも event 作成・記録などの計測処理が加わるので、計測を有効にした実行時間を無計測実行と同一視できません。

計測出力は stderr に `strata prefill timing: ...` として出ます。メイン行には入力 token 数、GPU timeline、wall time、host staging と、時間・割合が正の各フェーズが含まれます。続く host 行には chunk setup、chunk ごとの待ち、chunk 後の処理、PLE の時間が出ます。peer GPU が有効なら peer のフェーズ別時間・MoE layer 数なども出ます。ホスト側で計った chunk setup の内訳は SYCL 実装にあります。

## 文書・測定資料との照合

`docs/DETAILS.md` にはこの変数の説明を確認できませんでした。`docs/AMD_HIP.md` は Windows HIP の RX 6800 で `STRATA_MTP_SIDE_STREAM` の比較にこの計測を使い、「wait copy」の時間が 3,081 ms から 75 ms、12,642 ms から 288 ms になったと記録しています（7.9K-token と 30.4K-token prompt、IQ3_XXS、`STRATA_HIP_PROMPT_F16=1`）。同資料はその環境で decode と出力が同じだったとも記載します。これは資料に記載された特定環境の報告であり、この変数自体の性能効果を示す測定ではありません。`docs/OLDER_GPUS.md` も Tesla P40 の計測に使用したことを記載しています。

## 根拠

- 判定、event 記録・区間集計、フェーズ名、peer timer: `src/prefill/prefill.cpp:1999-2048,2054-2075`
- timer の生成、peer の有無による無効化、各呼び出しの計測と layer 同期での集計: `src/prefill/prefill.cpp:2140-2143,3241-3244`
- stderr 出力: `src/prefill/prefill.cpp:4267-4298`
- SYCL 側の判定、event 集計、setup 中の追加 queue wait とログ: `sycl/src/prefill/prefill.cpp:1982-2009,2011-2036,2223-2229,4613-4652`
- CUDA/HIP prefill target: `CMakeLists.txt:607-624`。SYCL の独立ビルド: `CMakeLists.txt:12-21`。
- 比較資料: `docs/AMD_HIP.md:219-225`, `docs/OLDER_GPUS.md:103-112`。
