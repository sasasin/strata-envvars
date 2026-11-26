# `STRATA_RAM_ADAPT_SKIP_TOP`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

`--serve` の resident RAM 適応 v2 が各層で RAM へ昇格させる候補から、GPU 外の候補のうち使用回数 `u[e]` が最も多いものを最大何件除外するかを指定します。値は `RamAdapt2::skip_top` に入り、既定値は `2` です。これは RAM 候補の除外数であり、GPU キャッシュの選択数やモデルの routing 自体は変更しません。候補除外後に RAM の入替候補をスコア順に選び、読み込みをステージします（`engine/src/program/generate.cpp:12334-12341,22862-22917`）。

## 値と判定

環境変数が未設定なら構造体初期値の `2` を使います。設定されている場合は `std::atoi` の結果を `std::max(0, ...)` で下限 0 に丸めます。空文字、先頭が数値でない文字列、`"0anything"` は 0 になり、`"2tail"` は 2、先頭空白と符号を含む `" +3x"` は 3 になります。小数点以下・数値の後ろは検査せず、`"1.9"` は 1 です。負数は 0 になります。整数として表現できない入力の範囲検査はありません。正数に上限クランプはありませんが、実際に除外する数はその層の eligible 候補数以下です（`engine/src/program/generate.cpp:12338,12348,22877-22887`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---:|---|---|
| GPU エンジンの `--serve` 経路で RAM 適応 v2 を実行する場合 | 2 件 | `1` 以上の整数変換結果。例: `1`, `2tail`, ` +3x` | `0`, 負数、空文字、`true`, `0anything` は変換後 0 件となり、この候補除外をしない |
| それ以外 | 読み取られないか、値を使うループに入らない | なし | この変数による効果なし |

`atoi` は全体の妥当性を検査しません。大文字小文字の区別はありません（文字列比較を行わないため）。`int` の表現範囲外の入力は Strata 側で検出・fallback されません（同 `:12343-12348`）。

## 有効になる条件

- 変数の読み取り・利用箇所は GPU 用 `strata` エンジンの `engine/src/program/generate.cpp` にあります（`engine/cmake/strata_gpu_engine.cmake:548-551`）。同名の実行時参照は Strata 全体の完全一致検索でこの 1 箇所だけで、SYCL / Metal の実装には見つかりません。
- `--serve` が必要です。値の読み取り自体が `if (o.serve)` の中にあります（`engine/src/program/generate.cpp:12302-12348`）。
- RAM 適応 v2 の `STRATA_RAM_ADAPT2` が `std::atoi` で非 0 と判定される必要があります。未設定、空文字、非数値文字列は v2 を有効化しません（同 `:12343-12348`）。
- `STRATA_RAM_ADAPT` が `atoi` 後に正である必要があります。これは `static` 初期化で一度読み、未設定時は 0 です（同 `:22843-22849`）。この値は各窓で新たに stage する入替ペア数の上限にも使われます（同 `:22913-22917`）。
- GPU 適応 tier の routing 使用量が必要です。`drive.d.usage` は `--adapt-every > 0`、`--adapt-swaps > 0`、GPU に全 expert が resident ではないこと、GPU cache slot があることを満たす場合に作られます（同 `:14999-15002`）。CLI は `--adapt-every` と `--adapt-swaps` を別々に設定できます（同 `:4058-4061,4202`）。既定値はそれぞれ 4 と 96 です（同 `:1045-1048,1084-1085`）。
- 実際の RAM 適応分岐では、最初の decode window ではないこと、前の GPU 適応 swap が未処理でないこと、非同期適応 job がないか idle であること、resident RAM complement が利用可能であること、単一 GPU で peer cache・remote expert optimization がなく、`--batch 0` であることが必要です（同 `:22847-22849`）。いずれかを満たさない窓ではこの候補除外を行いません。
- `STRATA_RAM_ADAPT_PER_LAYER` は RAM 入替候補数、`STRATA_RAM_ADAPT_PROMPT_W` は prompt routing seed による候補資格、`STRATA_RAM_ADAPT_CACHED_W` は page-cache 上の候補スコアに関係します。SKIP_TOP が順位付けする値は prompt seed を加えた値でなく `u[e]` です（同 `:12345-12348,22862-22900`）。キュー上限の `STRATA_RAM_ADAPT_QUEUE` で stage が拒否される場合もあります（`engine/src/core/expert_source.cpp:5014-5031`）。
- `STRATA_RAM_ADAPT2` が有効でない場合は、この変数の除外処理は通らず、同じ窓ループの従来 RAM 適応分岐が選ばれます（`engine/src/program/generate.cpp:22847-22849,22919-22922`）。

## 実行時の詳細

`--serve` の初期化時に、`RamAdapt2` の既定値 `skip_top = 2` を作り、その場で環境変数を一度読みます。リクエストごと・窓ごとの再読込や関数 `static` cache ではありません。サーバープロセス実行中に環境を変更しても反映されません。CLI 引数による直接の上書きはありません（`engine/src/program/generate.cpp:12302-12349`）。

適用窓では、各層について GPU 内の expert を除いたうえで、`u[e] + prompt seed` が 2 以上の expert を RAM への入力候補 `ins` とします。`skip_top > 0` の場合は、その候補から `u[e]` の降順で最大 `min(候補数, skip_top)` 件を `nth_element` で境界づけて除きます。同値が境界にある場合も `dropped < k` の条件により除外数は最大 k 件です。除外後の残りをスコア付けして RAM 内の resident expert と組み合わせ、`STRATA_RAM_ADAPT` の上限まで I/O thread 用キューに stage します（同 `:22862-22917`）。

したがって `0` は「全候補を除外」ではなくこの除外規則を無効にする値です。既定の `2` は各層で候補上位を最大 2 件除外します。GPU tier の選択規則はこの値で変更せず、routing・重みもこのフィルタ自体では書き換えません（同 `:22874-22887`）。完了済み stage の RAM への install は後続の適用窓境界で行われ、GPU tier が先に pair の expert を取った場合などは install されないことがあります（`engine/src/core/expert_source.cpp:5073-5093`）。

## ログと測定値

この変数の値、除外数、対象 expert を個別に表示するログはありません。`STRATA_RAM_ADAPT2` が有効なら、リクエスト集計に次の stderr 行が出ます（件数は実行時の値です）。これは stage 読み込み数と install / install skip の集計で、SKIP_TOP が除外した件数は示しません（`engine/src/program/generate.cpp:23801-23805`）。

空文字・非数値など `atoi` が 0 を返す設定でも、対象変数についての警告や終了処理はありません。表現範囲外の値は変換自体が未定義となり得るため、Strata のエラー経路や fallback は確認できません（`engine/src/program/generate.cpp:12343-12348`）。

```text
strata serve: resident RAM (STRATA_RAM_ADAPT2): %lld promotions read on the I/O thread, %lld installed, %lld skipped at the install (%lld of them: the GPU tier took one of the pair)
```

ソースコメントには「measured: 60% of the promotions skipped before this rule」とありますが、機種・OS・backend・モデル・設定・測定方法が示されていません。`docs/DETAILS.md:277-282` は従来の `STRATA_RAM_ADAPT` の説明で、この変数の測定値は記載していないため、測定結果としては扱いません。

## 根拠

- `engine/src/program/generate.cpp:12302-12349` — `--serve` スコープ、`RamAdapt2` の既定値、対象変数を含む環境値の読み取り。
- `engine/src/program/generate.cpp:14999-15002,22843-22849` — GPU 適応使用量の作成と RAM 適応分岐の条件。
- `engine/src/program/generate.cpp:22862-22922` — 層ごとの候補選定、skip_top 除外、スコアリング、stage と旧分岐。
- `engine/src/core/expert_source.cpp:5014-5031,5073-5093` — RAM stage queue と完了した読み込みの install / skip。
- `engine/src/program/generate.cpp:23801-23805` — `STRATA_RAM_ADAPT2` の集計ログ。
- `engine/cmake/strata_gpu_engine.cmake:548-551` — `engine/src/program/generate.cpp` を GPU エンジン executable に組み込む定義。
- `docs/DETAILS.md:277-282` — 従来の `STRATA_RAM_ADAPT` の説明との照合。対象変数の説明・測定値はなし。
