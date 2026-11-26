# `STRATA_BATCH_DF2_MAXX`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`strata generate --serve` の batch DFlash2 経路で、各 batch slot が 1 window に載せる DFlash2 draft 行数の上限を指定する。ターゲットモデルの window が検証する候補行を制限する設定で、生成 token 数の上限や DFlash2 の候補選択そのものを指定するものではない。値は batch window の構築時に `want` の上限として使われる（`engine/src/program/generate.cpp:17128-17146`）。

## 値と判定

batch window の準備時に `std::getenv` で読み、未設定または空文字なら `99`、それ以外は `std::atoi` の結果を `std::max(0, ...)` で 0 以上にする。文字列全体の妥当性検査はない。`atoi` は先頭の空白と符号を許し、数値として読める先頭部分を変換するため、たとえば ` 2tail` は 2、`0anything` と `true` は 0 になる。負値は 0 に丸められる。整数型で表せない値の `atoi` の結果は保証されないため、そのような値は有効な設定として扱えない（`engine/src/program/generate.cpp:16802-16808`）。

| 条件 | unset | 有効になる値（例） | 無効・実質無効になる値（例） |
|---|---|---|---|
| batch DFlash2 slot drafter が使われる経路 | 99。後段の上限で最大 7 行 | 空文字は unset と同じ。`1` は最大 1 行、`2tail` は最大 2 行、`7` 以上は DFlash2 固有上限の 7 行まで | `0`、`0anything`、`true`、`-1`、数値で始まらない文字列は 0 行 |
| batch DFlash2 slot drafter を使わない経路 | 効果なし | なし | 値は読み取られても draft 行数に適用されない |

DFlash2 の実装上の `kDrafts` は 7（8 行の block から anchor 1 行を除く）であり、正数の環境値はまずこの値で制限される。その後、window に残った spare rows の均等配分、slot の残り生成数、最大 context までの残り位置でも制限される（`engine/include/strata/core/dflash2.hpp:37-40`; `engine/src/program/generate.cpp:17121-17146`）。

## 有効になる条件

- DFlash2 対応の CUDA または HIP ビルドであること。DFlash2 の compile definition は CUDA/HIP 共通の GPU engine に置かれ、Metal と SYCL はその対象外（`engine/cmake/strata_gpu_engine.cmake:6-13`）。
- 実行が batch DFlash2 slot drafter を実際に使うこと。通常は明示的な `--draft dflash2`、`--batch` が 2 以上、`--serve`、`--draft auto` ではないこと、および同一 GPU 上の layer split ではないことが必要。`STRATA_BATCH_DF2=0` は無効化し、空でなく先頭文字が `0` ではない `STRATA_BATCH_DF2` はその他の自動選択条件を満たす場合に明示指定として使われる。layer split では batch groups が 1 以下の場合に自動選択される（`engine/src/program/generate.cpp:7822-7842`）。
- DFlash2 自体がロードされ、slot drafter の割り当てが成功していること。batch DFlash2 が動かない条件では警告または起動失敗の別経路があり、この上限は使われない（`engine/src/program/generate.cpp:8266-8273`, `8328-8348`）。
- `STRATA_BATCH_DF2_CONF` が draft chain をさらに短くすることがある。未設定・空文字時は `--draft-conf` が正ならその値、そうでなければ `0.35` が使われ、chain の確率積が閾値未満になる位置から後ろの行を除く。これは MAXX の上限を増やさない（`engine/src/program/generate.cpp:16803-16807`, `17139-17145`）。
- `--batch` の有効 slot 数と window に使える行数が少ない場合は、spare rows の配分が MAXX より小さくなる。slot の残り生成数と `--max-context` でも減る（`engine/src/program/generate.cpp:17121-17139`）。

## 実行時の詳細

環境変数は batch slot/window の状態を準備するときに一度読み、`const int df2_cap` に保持する。関数内 `static` ではなく、その batch engine の実行中に環境を変更しても再評価されない（`engine/src/program/generate.cpp:16802-16808`）。CLI に MAXX 専用の引数はない。`--draft-cap` は DFlash2 の verify window 幅を設定する別の引数であり、この変数を上書きしない（`engine/src/program/generate.cpp:1198`, `4163`, `8298-8303`）。

batch DFlash2 が動く window ごとに、アクティブ slot 数を数え、`win_cap - active slots` の余りを slot 間に分けて各 slot の `want` を決める。その `want` を DFlash2 固有行数、slot の残り出力数、context 残量、`df2_cap` の順に小さくし、必要に応じて `STRATA_BATCH_DF2_CONF` の条件でさらに削る。0 の場合は window に DFlash2 draft 行を載せない（`engine/src/program/generate.cpp:17121-17146`）。

ただし `STRATA_BATCH_DF2_DEFER=0` の場合、window に draft 行を載せない slot でも、window 後の DFlash2 drafter 処理は実行される。既定の defer 動作では行を載せなかった slot の taps を一時保存し、余り行が戻ったときに追いついて draft する。このため MAXX=0 は候補行の投入を止めるが、`STRATA_BATCH_DF2_DEFER=0` との組み合わせでは drafter の計算まで必ず止める設定ではない（`engine/src/program/generate.cpp:16808`, `17343-17374`）。

提案行はターゲット側の window に渡され、ターゲットの出力で受理された prefix だけが commit される。MAXX は提案行数を制限するもので、受理判定や生成上限を直接変更しない（`engine/src/program/generate.cpp:17260-17275`）。

## ログと測定値

MAXX の値や、それによる行数上限を直接表示するログは確認できない。DFlash2 の catch-up や draft 処理が失敗した場合は別途 stderr/stdout にエラーが出るが、MAXX の値が原因であることを示すログではない（`engine/src/program/generate.cpp:17148-17172`, `17343-17409`）。この変数自体の測定値は `docs/DETAILS.md` と実装箇所に記載がなく、ここでは示さない。

## 根拠

- `engine/src/program/generate.cpp:16802-16808` — batch 状態の生成時に環境値を取得し、`atoi` と 0 下限で cap を作る。
- `engine/src/program/generate.cpp:7822-7842` — batch DFlash2 と batch MTP の選択条件。
- `engine/src/program/generate.cpp:8266-8273`, `8328-8348` — DFlash2 のロード、slot drafter の割り当てと失敗時の扱い。
- `engine/src/program/generate.cpp:17121-17146` — window の spare rows を配分し、各上限を適用する。
- `engine/include/strata/core/dflash2.hpp:37-40` — DFlash2 固有の最大 draft 行数。
- `engine/cmake/strata_gpu_engine.cmake:6-13` — DFlash2 macro を定義する CUDA/HIP engine。
- `engine/src/program/generate.cpp:17343-17374` — draft 行の有無と defer 設定による window 後の処理。
- `engine/src/program/generate.cpp:17260-17275` — ターゲット側の候補受理と commit。
