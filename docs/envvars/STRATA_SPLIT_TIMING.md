# `STRATA_SPLIT_TIMING`

調査対象: Strata `main` の HEAD `a0116b2782a5b82622358c04a06496485d12b2d6`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

サーバーがリクエストを処理した後、各 verify stage のホスト側時間を stderr に出します。表示する内訳は GPU 到達待ち、CPU pool と plan、ホスト staging、commit で、各 stage の累積時間を verify window 数で割った値です。これは計測値を表示する診断用フックであり、GPU stage のイベント計測や decode の動作変更を有効にする設定ではありません。

## 値と判定

コードは環境変数の文字列を parse せず、`std::getenv("STRATA_SPLIT_TIMING") != nullptr` だけを確認します。

| 環境変数の状態 | 結果 |
|---|---|
| unset | stage timing の行を出さない |
| 空文字を含む、何らかの値が設定済み | stage timing の行を出す |

`1`、`0`、`false` などの値による違いはありません。大文字小文字や数値形式も検査しません。CLI オプションや設定ファイルによる上書きはありません。

## 有効になる条件

- CUDA 系または SYCL 系の `generate` 実装にあるサーバーのリクエスト処理後のログ経路で評価されます。通常の単発生成経路にはこの環境変数の読み取りはありません。
- `n_stages` 回のループで出力します。layer split がなければ1 stage（stage 0）、layer split があれば split の各 stage が対象です。単一 GPU か複数 GPU かを問わず、stage 数は実際の layer split 設定に従います。
- 環境変数を設定しても計時自体や stage の実行方式は切り替わりません。設定がなければ、この追加ログだけが抑止されます。

## 実行時の詳細

CUDA 系と SYCL 系の両方で、リクエスト後のサーバーログ処理に同じ判定と出力があります。設定値の有無は関数内の `static const bool` に保持され、最初にこの条件へ到達した時に一度だけ環境を読みます。その後プロセス中に環境を書き換えても再評価されません。

設定済みの場合、stage ごとに次の形式の行を stderr に出します（値は実装で計算した値です）。

```text
strata serve: stage 0: <windows> windows; per window: wait for the GPU <ms> ms, pool + plan <ms> ms, host staging <ms> ms, commit <ms> ms
```

`windows`、`ms_wait`、`ms_pool`、`ms_host`、`ms_commit` は verifier の統計です。表示値はそれぞれ `ms_wait / windows`、`ms_pool / windows`、`ms_host / windows`、`ms_commit / windows` です。window 数が0ならゼロ除算を避けるため分母を1にします。これらの統計は verify の実行中に加算され、同じ verifier に蓄積した範囲を表示します。出力頻度はリクエスト処理後です。

各指標の意味は verifier の実装経路で計上されるホスト時間の区分です。GPU の各 kernel の時間はこの環境変数では表示されません。`docs/DETAILS.md` の decode timing 説明は `STRATA_DECODE_TIMING` と、GPU 側計測用の `STRATA_VERIFY_PROFILE` を挙げていますが、`STRATA_SPLIT_TIMING` のこの stage 別ホスト時間ログについては説明していません。したがって、ここでは資料にない精度や性能上の効果を主張しません。

## 根拠

- `src/program/generate.cpp:12488-12497` — 設定有無の判定、stage ごとの統計参照、stderr の書式と平均計算。
- `sycl/src/program/generate.cpp:11615-11623` — SYCL 実装の対応箇所。
- `include/strata/core/verify.hpp:312-313` — verifier が保持する時間区分と window 数。
- `src/core/verify.cpp:2149-2166,2275-2276,2528,3450-3453` — CUDA verifier での host staging、GPU 待ち、commit の時間加算と pipelined verifier 統計の集約。
- `sycl/src/core/verify.cpp:2026,2149-2150,2299-2300,2704,3956-3958` — SYCL verifier の時間加算と統計集約。
- `docs/DETAILS.md:299-306` — 別の decode timing / GPU profile の説明。`STRATA_SPLIT_TIMING` の読み取り値や測定結果を裏付ける記述ではありません。
