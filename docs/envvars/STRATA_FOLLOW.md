# `STRATA_FOLLOW`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

サーバー要求の decode で、検証窓が通常選ぶ argmax の代わりにファイル内の token ID を強制する測定用フックです。通常設定用のフラグではなく、強制した token は後続の検証・採用判定・出力に使われます。したがって、単に logits を記録するだけの変数ではなく、生成結果を変えます。CUDA/HIP 実装は `engine/src/program/generate.cpp`、SYCL 実装は `engine/sycl/src/program/generate.cpp` にあります（CUDA/HIP: `21681-21685`, `22154-22162`, `23018-23030`; SYCL: `11750-11753`, `12780-12789`）。

## 値と判定

| ビルド | 未設定・空文字 | 設定時の読み方と有効な値 | 無効・不足時 |
|---|---|---|---|
| CUDA/HIP | 未設定または空文字なら `STRATA_FOLLOW` ファイルを読みません。 | 空でない値をファイル名として、プロセス内で最初にこの要求処理へ入った時に一度だけ開きます。全行を読み、各行から ASCII 数字の連続部分を `atoi` で `int32_t` に変換します。行は要求順の token ID 列です。 | ファイルを開けない場合は空リストとなり、強制値はありません。空行はその要求を強制しません。数字以外は読み飛ばすため、負号も区切り扱いになり `-7` は `7` として読み取られます。数値全体の妥当性、token ID の範囲は検査しません。 |
| SYCL | 未設定なら読みません。空文字も設定済みとして空のパスを `fopen` しますが、開けなければ値はありません。 | 要求開始時に指定ファイルを開き、`fscanf("%lld")` で空白区切りの符号付き整数を順に読み、各値を `int32_t` に cast します。負数も読み取ります。 | ファイルが開けなければ強制値はありません。数値でない文字に当たると `fscanf` が止まり、それ以前に読めた値だけを使います。token ID の範囲検査や clamp はありません。 |

CUDA/HIP は `getenv` の非 null に加えて先頭文字が NUL でないことを確認します。SYCL は非 null だけでファイルを開こうとします。両者とも `1` / `true` のような真偽値として parse するのではなく、値はファイルパスです（CUDA/HIP: `21686-21701`; SYCL: `11754-11762`）。環境変数値が `1`、`true`、`false` なら、それぞれその名前のパスとして扱われます。ファイル内容の例では、CUDA/HIP は `0` と `1` を ID として読み、`true` は ID を作りませんが、`0anything` は `0` を読みます。また `-7` は `7` になります。SYCL は `0`、`1`、`-7` を整数として読み、`true` は数値変換が止まる位置です。これらの内容例はファイルに書かれた token ID の判定を示します（CUDA/HIP: `21693-21697`; SYCL: `11756-11760`）。

## 有効になる条件

- 対象は CUDA/HIP または SYCL のサーバー要求 decode 経路です。コードは各要求の検証窓で強制値を反映します（CUDA/HIP: `22149-22162`, `23018-23030`; SYCL: `12774-12789`）。通常のファイル生成・prompt 処理だけを行う場合にこの decode 経路へ入らなければ適用されません。
- CUDA/HIP ではプロセス内で最初にこの処理が走る時点の環境変数とファイル内容が使われ、その後の環境変更やファイル更新は反映されません。読み込んだ各行は要求の処理順に一行ずつ割り当てられ、行が尽きた後の要求は直接の `STRATA_FOLLOW` による強制なしです。空行も要求順の位置を消費します（`21686-21707`）。
- CUDA/HIP では直接の `STRATA_FOLLOW` 行が空・不足などでその要求に値を与えなかった場合、別変数 `STRATA_FOLLOW_DIR` が設定されていれば prompt hash に対応する `<hash>.txt` を探す経路へ進みます。直接の値がある要求ではこの keyed lookup を使いません（`21709-21731`）。
- SYCL は要求ごとに環境変数を読み直してファイルを開きます。成功して読み終えるとそのファイルを削除します。よって同じパスを使う後続要求は、ファイルが再作成されなければ読み取れません（`11754-11762`）。
- 強制 ID が存在する位置では verify 結果の出力候補を置き換え、draft の一致判定にも使います。CUDA/HIP の両 decode ループと SYCL の decode ループで同じ方針です（CUDA/HIP: `22154-22162`, `23018-23030`; SYCL: `12780-12789`）。SYCL は token ID が負数なら上書きしません（`12782-12785`）。
- CUDA/HIP には `STRATA_FOLLOW_DIR` 以外の CLI 優先順位はありません。SYCL に `STRATA_FOLLOW_DIR` の参照はありません。別変数 `STRATA_FOLLOW_LOGPOS` が設定されると強制 token の log-probability 記録も試みますが、これは `STRATA_FOLLOW` の有効化条件ではありません（CUDA/HIP: `21703`, `23031-23040`; SYCL: `11763-11766`, `12790-12792`）。

## 実行時の詳細

CUDA/HIP ではファイルを静的ローカルの `fol_sets` に読み込み、`fol_next` を静的カウンターとして要求ごとに進めます。各検証窓で `produced_n + i` 番目の forced token があれば head の出力を置き換え、その forced token と次の入力 draft の一致に基づいて窓の採用を進めます。強制列の範囲外は argmax の出力のままです。serial decode と pipeline decode の両方に反映されます（`21686-21707`, `22154-22162`, `23018-23030`）。

SYCL では要求開始時に `fol` ベクトルを作り、各 verify 窓で `produced_n + i` 番目の値を最大 16 行まで `outv` に反映します。forced token と次の入力 window token の一致で採用数を決めます。強制列の範囲外や負の値は `outv` を置き換えません（`11750-11762` は読み取り部分、`12780-12790` は適用部分）。

同梱の `terminal/tools/force_check.py score --path decode` は continuation ごとに一行の token ID ファイルを作り、`STRATA_FOLLOW` と `STRATA_FOLLOW_LOGPOS` を engine 子プロセス環境へ設定します（`terminal/tools/force_check.py:189-202`）。

## ログと測定値

CUDA/HIP は、強制テキストに対応する検証行があれば stderr に `strata follow: %lld rows on the forced text, %lld of their picks were the forced token (%.2f%%)` 形式の集計を出します。ファイルの未設定・空・読み取り失敗だけを理由にするログは、この読み取り箇所にはありません（`23572-23574`）。

`STRATA_FOLLOW_LOGPOS` も有効で log-probability 出力に失敗した場合、CUDA/HIP は stderr に `strata serve: STRATA_FOLLOW_LOGPOS: %s` を出して処理を続けます（`23031-23040`）。SYCL は同出力処理が失敗すると stdout に `ERR %s` を出し、要求処理から `1` を返します（`12790-12792`）。これは関連する記録先の失敗経路であり、`STRATA_FOLLOW` ファイルの読み取り失敗を示すログではありません。

この文書では性能値を記載しません。`docs/INTEL_INT8_EXPERTS.md:84-90` には FP16 greedy continuation を teacher-force した測定記述がありますが、これは特定の int8 品質評価の条件と値であり、`STRATA_FOLLOW` 自体の一般的な性能・正確性を示すものではありません。

## 根拠

- `engine/src/program/generate.cpp:21681-21707` — CUDA/HIP の静的ファイル読み込み、行 parse、要求順割当。
- `engine/src/program/generate.cpp:21709-21731` — CUDA/HIP の `STRATA_FOLLOW_DIR` keyed fallback。
- `engine/src/program/generate.cpp:22149-22162` — pipeline decode で強制 token を適用。
- `engine/src/program/generate.cpp:23018-23040` — 通常 decode での適用と log-probability 記録。
- `engine/src/program/generate.cpp:23572-23574` — CUDA/HIP の forced token 集計ログ。
- `engine/sycl/src/program/generate.cpp:11750-11766` — SYCL の要求ごとの読み込み、ファイル削除、関連出力ファイルの初期化。
- `engine/sycl/src/program/generate.cpp:12774-12792` — SYCL の強制 token 適用と記録失敗時の終了経路。
- `terminal/tools/force_check.py:189-202` — 同梱測定ツールが continuation をファイル化して環境へ渡す経路。
- `docs/INTEL_INT8_EXPERTS.md:84-90` — 関連する品質測定の条件。測定記述としてのみ参照。
