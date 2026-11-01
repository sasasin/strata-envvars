# `STRATA_PIPELINE_DUMP`

調査対象: Strata `main` の HEAD `c62d5e3a15b40ea51c96aae9e8d36928965f53ab`（2026-11-01 時点）。調査開始時の作業ツリーは `## main...origin/main` で、未コミット変更はありません。

## 役割

SYCL 実装の `strata serve` が verify window を処理した後、GDN sequence state の合計値とハッシュをファイルへ追記する診断用変数です。サーバー内のシリアル経路と pipelined 経路の状態を比較するために使われます。値は出力先パスとして扱われ、生成計算や pipeline の有効・無効を切り替えません。

これとは別に、pipelined commit ごとの `n_keep` などを stderr に出す診断にも同じ変数の設定有無が使われます。どちらも SYCL 側の実装であり、CUDA ソースにはこの名前を読む箇所がありません。

## 値と判定

3 箇所すべてで `std::getenv(...) != nullptr` を使い、値の文字列や数値への変換はしません。

| 環境値 | 状態ダンプ | commit 診断 |
|---|---|---|
| 未設定 | 何も出力しない | 何も出力しない |
| 空文字 | ダンプ処理を行うが、空のパスでの `fopen` が成功しなければファイル行は書かれない | stderr に診断行を出す |
| 空でない文字列 | 文字列全体をファイルパスとして `fopen(path, "a")` に渡す | 値の内容に関係なく stderr に診断行を出す |

真偽値、数値、境界値、無効文字列としての検証はありません。CLI 引数や他の環境変数による上書き・優先順位もありません。`STRATA_PIPELINE_DEBUG` を設定しなくても、これらの直接読み取りは行われます。

## 有効になる条件

- 対象の読み取りは `sycl/src/program/generate.cpp` と `sycl/src/core/verify.cpp` にだけあります。CUDA 実装や通常の単一 GPU decode のソースに同名の読み取りは確認できません。
- 状態行は `strata serve` の request decode ループで、シリアル window の commit 後、または pipelined window の verdict 後に出力されます。シリアル行は通常のシリアル経路でも記録されます。pipelined 行には、pipeline が選択され、`pl_want` が成立し、リクエストがキャンセルされておらず、まだ出力上限に達していないことが必要です。`pipe` は `--pipeline-windows > 0`、2 stage、同一 GPU 上の split ではないことなどを要求します。
- `--pipeline-windows` 自体の backend / 起動条件は別途あり、資料では SYCL の AMD RDNA4、Intel Arc B-series などの既定条件と NVIDIA の opt-in が説明されています。変数が設定されても pipeline 起動条件を満たさなければ、pipelined 行は出ず、シリアル行だけになる場合があります。
- commit 診断は `Verifier::pl_commit_async()` の呼び出しごとに出ます。実際の呼び出し経路には pipelined request 内の commit と rollback の再 commit があります。

根拠: `sycl/src/program/generate.cpp:7325-7329,11029-11049,11629-11630,11874-11876`; `sycl/src/core/verify.cpp:4058-4066`; `docs/MULTI_GPU.md:181-197`。

## 実行時の詳細

シリアル側では window の commit が成功した後に `ss.gdn_state` を host vector にコピーして待ち合わせます。状態値を recurrence state と convolution history に分けて走査し、各要素の合計とハッシュを作成し、ファイルを追記モードで開けた場合に `pos ... serial rec ... cnv ...` の行を書きます。

pipeline 側では verdict の後に stage 0 の stream から同じ GDN state をコピーして待ち、同様にハッシュと合計を計算します。書き込む行は `pos ... windows ... rec ... cnv ...` です。どちらのダンプも各ブロック内の function-local `static` ポインタに環境値を保存し、最初にそのコード位置へ到達したときに一度だけ読みます。commit 診断にも別の `static` cache があり、最初の `pl_commit_async()` 呼び出し時に設定有無を保存します。

ダンプ path の `fopen` が失敗した場合はその行を出力しません。該当ブロックにはファイル open の失敗を stderr に報告したり処理を失敗させたりする分岐はありません。ただし、path が設定されていると open の成否にかかわらず state copy の wait と hash 計算までは実行されます。commit 診断は stderr に `strata commit: n_keep=%d T=%d pos0=%lld self_skip=%d` の形式で出ます。この変数自体に、終了コードやエラー経路を変える処理はありません。

根拠: `sycl/src/program/generate.cpp:11629-11664,11866-11881,11882-11909`; `sycl/src/core/verify.cpp:4060-4067`。

## 根拠

- 候補名の全参照を `rg -n --hidden --glob '!.git/**' 'STRATA_PIPELINE_DUMP'` で確認しました。実読み取りは `sycl/src/core/verify.cpp:4063` と `sycl/src/program/generate.cpp:11629,11875` の3箇所です。他の参照はコメントです。
- state dump の値判定、同期コピー、state の分割・集計・追記: `sycl/src/program/generate.cpp:11625-11664,11871-11909`。
- pipelined の成立条件と経路: `sycl/src/program/generate.cpp:7325-7329,11037-11049`。
- commit 診断と commit / event error の戻り経路: `sycl/src/core/verify.cpp:4058-4067,4110-4139`。
- pipeline の実行条件の説明: `docs/MULTI_GPU.md:181-197`。
