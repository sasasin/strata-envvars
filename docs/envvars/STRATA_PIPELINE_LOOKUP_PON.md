# `STRATA_PIPELINE_LOOKUP_PON`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

パイプライン化された speculative decode で、suffix lookup が見つけた A の続きから作る後続ウィンドウ B に設定する `p_on`（直前のウィンドウが経路上にあるという見積もり）を指定する。既定値は `0.75`。これは lookup 自体を有効にする設定ではなく、lookup が作った B を使うための見積もり値である。CUDA 系では B の起動判定にも使い、`STRATA_PIPELINE_LOOKUP_RUN` が有効な場合の B の次の lookup ウィンドウにも同じ値を使う。SYCL 系は B の作成に使うが、CUDA 系にある後続 lookup ウィンドウの処理は確認できない。実装は `engine/src/program/generate.cpp` と `engine/sycl/src/program/generate.cpp` にある。

## 値と判定

両実装とも `pipe_dbg_env("STRATA_PIPELINE_LOOKUP_PON")` の戻り値を `std::atof` で `float` に変換する。helper は `STRATA_PIPELINE_DEBUG` が有効でなければ対象名を読まず `nullptr` を返すため、対象変数は実質的に debug gate 付きである。debug gate は最初に helper が呼ばれた時に一度だけ評価され、値が未設定・空・先頭文字が `0` なら無効、それ以外の非空文字列（例: `1`, `true`, `false`, ` 0`）なら有効となる。先頭文字だけを見ており、trim や大文字小文字判定はしない（CUDA: `engine/src/program/generate.cpp:681-687`、SYCL: `engine/sycl/src/program/generate.cpp:325-339`）。

| 条件 | `STRATA_PIPELINE_LOOKUP_PON` が未設定 | 設定値の扱い |
|---|---|---|
| `STRATA_PIPELINE_DEBUG` が無効（未設定、空、`0` / `0anything`） | `pipe_dbg_env` が `nullptr` を返し、`0.75` | 値を読まない。 |
| debug gate が有効で対象変数が未設定 | `0.75` | — |
| debug gate が有効で対象変数が設定済み | — | `atof` が認識した数値接頭辞を float に変換する。空文字、`0`、`0anything`、`true` など数値を開始しない文字列は `0` となる。`0.5tail` は `0.5`、`-1` は `-1`。空白で始まる数値も `atof` の変換対象。 |

変換結果が正数かどうかだけを後段で確認し、数値全体の妥当性検査や範囲制限はない。したがって `0` 以下や数値に変換できない文字列は lookup 由来の B を作らず、正数（`1` 超を含む）は B の見積もり値として使われる。未設定時の `0.75` も同じ条件に従う（CUDA: `engine/src/program/generate.cpp:22067-22072, 22087-22099`、SYCL: `engine/sycl/src/program/generate.cpp:12074-12080, 12095-12107`）。

## 有効になる条件

- `STRATA_PIPELINE_DEBUG` が有効であること。無効なら明示した対象値も読み取られず、既定の `0.75` が使われる。
- パイプライン decode の経路に入ること。CUDA 系では `--pipeline-windows` が正で、2 段以上の有効な layer split が必要（`engine/src/program/generate.cpp:13263-13267`）。SYCL 系では2段の layer split が必要（`engine/sycl/src/program/generate.cpp:7712`）。対象の lookup コードはさらに `pl_want` の decode 分岐内にあり、`pl_pw >= 2` と snapshot 利用可能性を要する（CUDA: `engine/src/program/generate.cpp:21810-21821`、SYCL: `engine/sycl/src/program/generate.cpp:11783-11795`）。
- その decode 要求が serial 経路に戻されず、キャンセル済みでなく、生成上限にも達していないこと（同上）。CUDA/SYCL の `pl_serial` 判定は履歴ペナルティまたは coupled draft sampling がある要求を serial にする（CUDA: `engine/src/program/generate.cpp:21811-21821`、SYCL: `engine/sycl/src/program/generate.cpp:11783-11795`）。
- B の作成には `suffix_draft > 0`、先頭ウィンドウではないこと、suffix lookup に候補があり drafter の先頭予測と一致すること、policy が lookup を選ぶこと、lookup 続きが少なくとも1 tokenあること、既に B が作成されていないことが必要。`p_on <= 0` なら B は作成されない（CUDA: `engine/src/program/generate.cpp:22073-22099`、SYCL: `engine/sycl/src/program/generate.cpp:12081-12107`）。
- CUDA 系で lookup の B のさらに次も同じ lookup から作る場合は、別変数 `STRATA_PIPELINE_LOOKUP_RUN` が `atoi` で非ゼロとなる必要がある。未設定なら無効。これは対象変数の読み取りを置き換えず、後続ウィンドウ作成を追加で許可する（`engine/src/program/generate.cpp:20273-20279, 22469-22498`）。SYCL 実装には `STRATA_PIPELINE_LOOKUP_RUN` の読み取り・この後続 lookup 分岐がない。
- `--pipeline-windows` などの CLI 値が対象変数の数値を上書きする分岐はない。`STRATA_PIPELINE_SWITCH` のファイル読み取りにも `lookup_pon` の項目はない（`engine/src/program/generate.cpp:20284-20302`）。

## 実行時の詳細

`pl_lookup_pon` は pipeline decode 本体にある関数ローカル `static const float` で、対象環境変数と debug gate をそのプロセスで初めて初期化箇所に到達した時に読み、以後はキャッシュ値を使う。実行中に環境を変更しても反映されない。debug gate 自体も helper 内の `static const bool` で初回評価後は変わらない（CUDA: `engine/src/program/generate.cpp:684-687, 22067-22072`、SYCL: `engine/sycl/src/program/generate.cpp:337-340, 12074-12080`）。

lookup が A の続きに B の token を見つけると、実装は B にその token 列と `pl_lookup_pon` を設定して `ready` / `made` にする。CUDA は加えて `row=10`, `lk=true`, `gate_pass(B.p_on, true)` を設定する。CUDA の gate は `STRATA_PIPELINE_THETA` が使われる場合 `p_on >= theta`、それ以外は `STRATA_PIPELINE_HIT_MIN` に基づく lookup 用 calibration 行の判定で、値が正でも gate に通らなければ投機起動されない（`engine/src/program/generate.cpp:21850-21870, 22087-22104`）。SYCL は B に `p_on` を設定するが `gate_pass` を呼ばず、後続の起動側で `B.p_on >= theta` を判定する（`engine/sycl/src/program/generate.cpp:12095-12107, 12336-12339`）。

CUDA で `STRATA_PIPELINE_LOOKUP_RUN` が有効なとき、B が lookup 由来で、suffix drafting が続いていれば、B の後ろを検索して次のウィンドウ `nB` を作り、`nB.p_on` にも同じ値を設定する。その分岐が成立しない場合は、通常の drafter chain を使う（`engine/src/program/generate.cpp:22469-22505`）。

## ログと測定値

この変数の未設定・値の採用・無効値について専用の警告やエラー出力はない。lookup 由来の B を作った箇所では trace イベント `tre("CD", ..., 3, 1000 * p_on)` を記録するが、これは pipeline trace の仕組みを通じたイベントであり、この環境変数専用の stderr/stdout メッセージではない（CUDA: `engine/src/program/generate.cpp:22103, 22498`、SYCL: `engine/sycl/src/program/generate.cpp:12107`）。パイプライン処理の準備自体に失敗した場合は `ERR %s\n` を stdout に出して `return 1` するが、これはこの変数の値判定に対するエラーではない（CUDA: `engine/src/program/generate.cpp:21821-21825`）。`docs/DETAILS.md` にこの変数名やこの値の測定条件付き結果は見つからなかったため、性能値は記載しない。

## 根拠

- debug gate と helper: `engine/src/program/generate.cpp:681-687`、`engine/sycl/src/program/generate.cpp:325-339`
- パイプライン decode の到達条件: `engine/src/program/generate.cpp:13263-13267, 21810-21821`、`engine/sycl/src/program/generate.cpp:7712, 11783-11795`
- 値の読み取りと lookup B の作成: `engine/src/program/generate.cpp:22063-22104, 22469-22498`、`engine/sycl/src/program/generate.cpp:12071-12107`
- CUDA 系の別条件: `engine/src/program/generate.cpp:20273-20279, 21850-21870`
