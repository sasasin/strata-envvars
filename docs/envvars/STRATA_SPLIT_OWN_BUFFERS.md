# `STRATA_SPLIT_OWN_BUFFERS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

複数 GPU の layer split で、各 stage が prompt prefill 用バッファを自分の GPU メモリに置ける余裕があるとき、expert cache の末尾 slot を貸し出さずに残すかを制御する。unset（既定）ではこの判定を許可し、実際にバッファ必要量と空きメモリを照合して余裕がある stage だけ貸し出しを省く。値が `0` で始まる場合はこの自動判定を止め、通常の借用判定を適用する。対象は layer split の prompt buffer / expert-cache loan で、生成 token や expert の選択規則を直接変更する設定ではない（CUDA: `engine/src/program/generate.cpp:12769-12796`、SYCL: `engine/sycl/src/program/generate.cpp:7402-7445`）。

CUDA の resident CPU expert 経路では、同じ設定を RAM 側に保持する split の lend-region 算定にも使う。stage が GPU 上で自前バッファを賄える場合、その stage の lend region を RAM コピーにも含めない（`engine/src/program/generate.cpp:11933-12041`）。

## 値と判定

各箇所は `std::getenv` の結果を `nullptr` と比較し、設定時は `v[0] != '0'` を評価する。文字列全体の parse はなく、空文字列は `v[0] == '\0'` のため有効扱い。`0`、`0anything`、`01` は無効扱いで、`1`、`true`、`false`、先頭空白のある ` 0`、その他 `0` 以外で始まる値は有効扱いとなる。大文字小文字、空白、数値妥当性の検査はない（CUDA: `engine/src/program/generate.cpp:12002-12005,12775-12778`、SYCL: `engine/sycl/src/program/generate.cpp:7407-7411`）。

| 読み取り箇所 | unset | 設定時に有効 | 設定時に無効 |
|---|---|---|---|
| CUDA resident CPU expert の lend-region 算定 | 有効 | 空文字、`1`、`true`、` 0` など先頭が `0` 以外 | `0`、`0anything`、`01` |
| CUDA / SYCL serve の stage loan 判定 | 有効 | 空文字、`1`、`true`、` 0` など先頭が `0` 以外 | `0`、`0anything`、`01` |

## 有効になる条件

- serve の loan 判定は複数 stage の layer split でのみ対象になる。`--layer-split` は `--serve` を必要とし、split は `--expert-profile` も必要とする（`engine/src/program/generate.cpp:4848-4853,4895-4898`）。
- 通常の loan 経路では `--no-prefill-borrow` が指定されておらず、expert profile があり、VRAM expert cache があることが前提。これらを満たさない場合 `pf_parts` が作られず、この設定による loan 抑制判定は実行されない（`engine/src/program/generate.cpp:6821,12449-12455`）。
- chunk が正で、serve 側の split 構成が成立している必要がある。値が有効でも、各 stage の空きメモリが `Prefill::bytes_needed(...) + 3 GiB` 未満なら、その stage は引き続き cache slot を貸す。空きメモリ照会に失敗した場合も、その stage の loan は抑制されない（CUDA: `engine/src/program/generate.cpp:12747-12792`、SYCL: `engine/sycl/src/program/generate.cpp:7386-7442`）。
- `--no-prefill-borrow` などにより loan 自体が使われない経路では、自前バッファになるかどうかをこの変数が切り替えるわけではない。単一 GPU の loan にも split 専用の stage 判定は適用されない（`engine/src/program/generate.cpp:12449-12455,12769-12796`）。
- CUDA resident CPU expert の RAM コピー判定は、さらに `--resident-cpu-experts` 経路で、`pf_borrow`、resident cache、正の prefill chunk、複数 GPU split、stage の存在を要する。条件を満たさない場合、この変数による RAM lend-region 判定は行われない（`engine/src/program/generate.cpp:11908-11912,11964-12041`）。

## 実行時の詳細

CUDA serve は chunk 決定後、各 `PfPart` の `bytes_needed` と現在の device free memory を調べ、設定が有効で空きが必要量 + 3 GiB 以上なら `p.first` と `p.first_now` を `-1` にして、その stage の prompt buffer に cache slot を貸さない。空きが足りない、またはメモリ照会に失敗した stage では従来の末尾 slot loan を続ける。これにより全 stage が必ず自前バッファになるわけではなく、stage ごとの条件で混在し得る（`engine/src/program/generate.cpp:12765-12796`）。SYCL の同等箇所も stage ごとに同じ free-memory 閾値を調べて loan を省く（`engine/sycl/src/program/generate.cpp:7397-7445`）。

CUDA の resident CPU expert 経路は、serve の scan が取り得る最大 chunk のバッファ量を使って stage ごとの lend region を算定する。設定が有効でその時点の free memory が `need + 3 GiB` 以上なら、その stage の region を作らず、そうでなければ cache slot の末尾から必要領域を作り `src.stage_lend_regions` に渡す（`engine/src/program/generate.cpp:11964-12041`）。この読み取りは serve 判定とは別の `static` ローカル値である。

serve 判定の `static const bool` は CUDA と SYCL それぞれの該当ブロックに初めて到達したときに初期化され、そのプロセス内では値を cache する。CUDA の resident CPU expert 判定も別の `static` であり、該当箇所の初回到達時に独立して cache する。したがってプロセス起動後に環境を変更しても、初期化済みの判定には反映されない（CUDA: `engine/src/program/generate.cpp:12002-12005,12775-12778`、SYCL: `engine/sycl/src/program/generate.cpp:7407-7411`）。子プロセスへの転送・上書きはこの読み取り箇所にはない。

## ログと測定値

この変数名を含む有効・無効ログはない。余裕があり loan を省いた CUDA / SYCL stage では stderr に `strata serve:   CUDA%d keeps its own prompt buffers (%.2f GiB of %.2f GiB free): no loan` が出る（CUDA: `engine/src/program/generate.cpp:12783-12790`、SYCL: `engine/sycl/src/program/generate.cpp:7428-7440`）。loan が残る場合は `strata serve:   CUDA%d prompt path borrows ...` が出る。どの stage にも loan がない場合は `strata serve: the prompt path allocates its own buffers (too few cache slots to borrow)` が出る（CUDA: `engine/src/program/generate.cpp:12924-12953`、SYCL: `engine/sycl/src/program/generate.cpp:7464-7476`）。

自前バッファ初期化に失敗した場合、CUDA serve はエラーを表示して終了する前に、戻り値が `2` でより小さい chunk が残っていれば小さい chunk で再試行する。最終的に再試行できない場合は `strata serve: <error>` を出して `1` を返す（`engine/src/program/generate.cpp:13101-13140`）。環境変数固有の測定値は Strata の資料・実装に確認できないため記載しない。`docs/DETAILS.md` にもこの変数の記載は見つからなかった。

## 根拠

- 候補名の全ソース参照と判定: `engine/src/program/generate.cpp:12002-12005,12775-12778`、`engine/sycl/src/program/generate.cpp:7407-7411`。
- CUDA resident CPU expert の RAM lend-region 算定: `engine/src/program/generate.cpp:11908-11912,11933-12041`。
- split / serve / profile 条件と通常の loan 経路: `engine/src/program/generate.cpp:4848-4853,4895-4898,6821,12449-12455,12765-12796`。
- serve ログと初期化失敗時の再試行・終了: `engine/src/program/generate.cpp:12924-12953,13101-13140`、`engine/sycl/src/program/generate.cpp:7464-7476`。
