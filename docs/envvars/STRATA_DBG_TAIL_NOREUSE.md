# `STRATA_DBG_TAIL_NOREUSE`

調査対象: Strata `main` の HEAD `c77572806996349b49995e4f98d41b5294d36a21`（`2026-11-17` 時点）。

## 役割

`--serve` のプロンプト読み込みで、貸出中の expert-cache slot を次の segment に再利用する判定から、短い末尾 chunk 用の tail 容量チェックを外す診断用スイッチです。通常は要求 chunk と既存 loan の chunk が合うだけでは再利用せず、segment を既存 loan の chunk で読んだときの末尾に必要な容量も確認します。この変数を有効にすると chunk の大きさだけで再利用し、tail 容量が不足する segment は後続の prefill 検査でエラーになります。生成 token や選択結果を変える設定ではなく、プロンプト読み込みの slot loan 再利用経路を変えます。`src/program/generate.cpp:18423-18435`

## 値と判定

`std::getenv` の返す文字列の先頭 1 文字だけを `1` と比較します。未設定と空文字は無効です。値全体の parse や数値妥当性の確認はなく、`1`, `1anything` は有効、`0`, `0anything`, `true`, ` 1` は無効です。負値を含め `1` で始まらない文字列は無効です。既定値は無効で、CLI 引数や他の変数による上書きはありません。`src/program/generate.cpp:10446-10448`

| 条件 | unset | 有効になる値 | 無効になる値 |
|---|---|---|---|
| `--serve` の tail-aware loan 再利用判定 | tail 検査を行う | 先頭文字が `1`（tail 検査を省き、chunk だけで再利用） | 空文字を含め先頭文字が `1` でない値（tail 検査を行う） |
| 下記の tail-aware 条件を満たさない場合 | chunk だけで再利用判定 | 同じ | 同じ（この変数による差はない） |

## 有効になる条件

- `--serve` の永続 engine で、prompt の segment に対する slot loan 処理を通ること。ワンショットの generate 側にも loan 計算はありますが、この変数による再利用分岐はありません。`src/program/generate.cpp:10365-10386`、`src/program/generate.cpp:18368-18435`、`src/program/generate.cpp:21605-21631`
- tail-aware 判定 `tail_ok` が真であること。`STRATA_PREFILL_TAIL_LOAN` が先頭 `0` でなく、prompt path が 1 loan participant、stage 分割なし、multi-GPU なし、peer device なし、`--prefill-head-alias` なし、`--batch` が 1 以下である必要があります。`STRATA_PREFILL_TAIL_LOAN=0` ならこの条件を外れ、chunk-only 判定が通常経路になります。`src/program/generate.cpp:10442-10448`、`src/program/generate.cpp:18420-18431`
- loan の layout が fused buffer を使い、tail 容量が実質的に制限される場合にだけ、この変数で再利用可否が変わり得ます。非 fused layout の `tail_room()` は `INT64_MAX` を返すため、tail check を含む判定でも chunk 条件以外で再利用を拒みません。`src/prefill/prefill.cpp:2851-2859`

## 実行時の詳細

値は `generate.cpp` 内の関数ローカル `static const bool` 初期化子で初回評価され、そのプロセス内でキャッシュされます。したがって実行中に環境値を変更しても反映されません。`src/program/generate.cpp:10446-10448`

serve の各 segment で、既存 loan があるとき、通常の tail-aware 経路は `reuse_ok(want, tokens, lent_chunk, tail_room, floor)` を評価します。これは `want <= lent_chunk` に加え、segment を loan 自身の chunk で読んだときの末尾に必要な tail が loan の tail 容量以下であることを要求します。有効値ではこの条件式が `want <= lent_chunk` に置き換わるため、chunk が収まれば loan を再利用し、再配置・再貸出を行いません。`src/program/generate.cpp:18420-18435`、`include/strata/prefill/loan_rules.hpp:68-73`

再利用された loan の tail が不足し、fused layout の短い chunk が `tail_room()` を超えると、`Prefill::run_impl` は `prefill: a chunk of <T> tokens below the stream floor does not fit the fused layout's tail of <N> tokens` を error に設定して読み込みを失敗させます。serve 側は stderr に `strata serve: <error>`、stdout に `ERR <error>` を出して当該要求の処理を失敗させます。`src/prefill/prefill.cpp:4165-4172`、`src/program/generate.cpp:19402-19405`

## ログと測定値

この変数自体を有効化・無効化したことを示すログは見つかりませんでした。tail 容量を超えた場合は上記の stderr と `ERR` が観測できます。Strata の `docs/DETAILS.md` および関連する `docs/SETTINGS.md` にこの debug 変数の説明や、この変数に結び付いた測定値はありません。ソースコメントは backstop 検証用としていますが、ここでは実行・測定していません。`src/program/generate.cpp:10446-10448`、`src/prefill/prefill.cpp:4165-4172`

## 根拠

- `src/program/generate.cpp:10442-10448` — 関連する tail loan 設定と対象変数の読み取り・cache。
- `src/program/generate.cpp:18420-18435` — tail-aware 条件、通常の再利用判定、有効時の chunk-only 判定。
- `include/strata/prefill/loan_rules.hpp:68-73` — loan 再利用時の chunk / tail 条件。
- `src/prefill/prefill.cpp:2851-2859` — layout の tail 容量と fused buffer 条件。
- `src/prefill/prefill.cpp:4165-4172` — tail 超過時の error。
- `src/program/generate.cpp:19402-19405` — serve の stderr / stdout エラー出力。
