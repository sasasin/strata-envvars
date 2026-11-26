# `STRATA_VERIFY_ALL_SLOTS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-26` 時点）。

## 役割

SYCL 版 `strata generate` の expert cache を GGUF からパイプライン充填したとき、充填した全 slot を device から読み戻し、GGUF の blob と byte 単位で比較する診断フック。設定しても cache の選択・slot の配置を変える分岐には使われず、比較と診断ログが追加される。通常の slot 0 の検証はこの変数と独立して行われる（`engine/sycl/src/program/generate.cpp:5256-5257,5326-5369,5410-5418`）。

## 値と判定

唯一の読み取りは `std::getenv("STRATA_VERIFY_ALL_SLOTS") != nullptr`。値の内容は変換・比較されず、環境変数が存在するかだけを見る（`engine/sycl/src/program/generate.cpp:5326`）。

| 条件 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| SYCL のパイプライン expert-cache fill | 追加の全 slot 比較なし | 空文字、`0`、`1`、`true`、`false` など、環境変数が存在すればすべて有効 | なし（値の妥当性検査なし） |

大文字小文字、空白、数値形式の検査や境界値処理はない。CLI 引数や別の変数による値の上書きもない。`docs/INTEL.md` は `STRATA_VERIFY_ALL_SLOTS=1` と記すが、実装は文字列 `1` との比較ではなく存在判定である（同 `:5326`）。

## 有効になる条件

- この読み取りは `engine/sycl/src/program/generate.cpp` にあり、CUDA/HIP/CPU 実装に同名の読み取りはない（候補名の全参照を検索した結果）。
- `profile` が空でなく `srcp` が存在する expert-cache fill のうち、`piped` が真の経路だけが callback を作る。`piped` は `srcp == &gguf_src`、`--stream-experts` による GGUF source、per-layer admission 無効、`STRATA_FILL_SERIAL` が未設定という条件（`engine/sycl/src/program/generate.cpp:4710-4725,5257,5270`）。
- per-layer fill とシリアル fill ではこの変数による追加比較は行われない。値が存在しても上記条件を満たさない実行経路では無視される（同 `:5270-5271,5371-5384`）。
- 起動やプロファイル読み込みの有無自体をこの環境変数が有効化するわけではない。profile fill が行われない場合 callback は設定されない（同 `:5257,5326-5328`）。

## 実行時の詳細

読み取りは pipeline fill が終わった後、当該 `generate` 実行で一度行われる。static cache はなく、プロセス起動後に環境を変更しても、この読み取りより前に反映された値が判定される。設定されていれば、fill 対象の `(layer, expert, slot)` 一覧を保持する callback を作り、直ちに `after the fill` として比較する。さらに session が立ち上がった後、`session up` として同じ slot 群を再比較する（`engine/sycl/src/program/generate.cpp:5325-5370,6002-6005`）。

各比較では SYCL queue を待ち、GGUF blob を再読込し、slot の device memory を host buffer にコピーして `memcmp` する。違いがある slot ごとに差分 byte 数と最初・最後の offset を出し、最後に不一致 slot 数と最初の fill index をまとめる。GGUF の再読込に失敗した場合も `bad` 件数に加算されるが、その slot の mismatch 行は出ない。callback の戻り値による処理中断や非ゼロ終了はなく、比較結果は診断として出力される（同 `:5328-5368`）。

この診断のための追加 GGUF 読み込み・device-to-host コピー・queue wait は発生する。初回 pipeline fill 自体の read/copy 失敗はそれぞれ `the profile fill could not read an expert from the GGUF` を stderr に出して `return 1` するが、これは環境変数固有の分岐ではない（同 `:5287-5292,5307-5323`）。

## ログと測定値

不一致 slot ごとに stderr へ次の形式で出力する（数値部分は実行時の値）。

```text
strata generate: STRATA_VERIFY_ALL_SLOTS (<when>): fill <i> (layer <l> expert <e>) slot <slot> at <ptr>: <different-bytes> of <blob-bytes> bytes differ, first at <offset>, last at <offset>
```

各比較の最後には、不一致がなくても次の集計行が出る。`<when>` は `after the fill` または `session up`。

```text
strata generate: STRATA_VERIFY_ALL_SLOTS (<when>): <bad> of <slots> slots differ from the GGUF (first at fill <index>)
```

一致時は `bad` が `0`、`first at fill` は初期値 `-1`。不一致があると、既定で最初に見つかった slot について optional な `STRATA_VERIFY_DUMP` が指定されていれば `<value>/slot<slot>.got` と `.want` を書き出す。`STRATA_VERIFY_FIND` が存在し、不一致が最初の 2 件以内で最初の差分位置から 4,160 byte 以上 blob が続く場合は、誤データの出所を探す追加ログを出す。これらの分岐も値そのものではなく存在有無で判定する（`engine/sycl/src/program/generate.cpp:5332-5368`）。測定値の記載はない。

## 根拠

- `engine/sycl/src/program/generate.cpp:5256-5271` — callback の宣言、profile fill と pipeline 条件。
- `engine/sycl/src/program/generate.cpp:5325-5369` — 環境変数読み取り、slot 全件の比較、補助診断とログ。
- `engine/sycl/src/program/generate.cpp:6002-6005` — session 起動後の再比較。
- `engine/sycl/src/program/generate.cpp:5410-5418` — 変数と独立した slot 1 件の通常検証。
