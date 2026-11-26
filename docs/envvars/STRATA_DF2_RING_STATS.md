# `STRATA_DF2_RING_STATS`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

CUDA 系と SYCL 系の DFlash2 drafter が request を開始するとき、リング再構築の統計行を stderr に出すかを切り替える診断用変数。設定値そのものは読まず、`std::getenv(...) != nullptr` で設定の有無だけを判定する。リング再構築やドラフトの計算を有効化する設定ではなく、これらのログ以外の処理分岐を変えない（`engine/src/core/dflash2.cpp:891-903,954-976,1007-1034`、`engine/sycl/src/core/dflash2.cpp:585-597,633-655,685-712`）。

実装は CUDA 系 `Dflash2Drafter::rebuild` / `begin_request` と SYCL 系の同名関数にある。通常の生成経路では、`use_df2` のとき serve の request ごとに `begin_request` が呼ばれる（CUDA: `engine/src/program/generate.cpp:20170-20185`、SYCL: `engine/sycl/src/program/generate.cpp:11105-11118`）。

## 値と判定

| build / 判定箇所 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA 系・SYCL 系の `begin_request` 内の統計行 | 統計行を出さない | `1`、`0`、`true`、`false`、空文字など、環境変数が存在すればすべて有効 | なし。文字列比較・数値変換・空白処理・範囲検査はない |
| CUDA 系・SYCL 系の `rebuild` 内の欠落位置行 | 欠落位置行を出さない | 値を問わず設定されていれば、その rebuild 内で欠落と数えた最初の 8 位置まで出す | なし。設定有無以外の値判定はない |

`STRATA_DF2_RING_LOG=0` などでリングログが無効、または staging 確保失敗で無効になった場合、`begin_request` は統計行の判定箇所に到達しない。したがって本変数を設定してもその経路の統計行は出ない（CUDA: `engine/src/core/dflash2.cpp:822-834,970-977`、SYCL: `engine/sycl/src/core/dflash2.cpp:215-225,648-655`）。

## 有効になる条件

- 対象実装を含む CUDA 系または SYCL 系 engine build であること。候補名の実装参照は `engine/src/core/dflash2.cpp` と `engine/sycl/src/core/dflash2.cpp` に限られる。CUDA 系の生成側は `STRATA_HAVE_DFLASH2` build guard 内にあり、`use_df2` が true の request で呼ばれる（`engine/src/program/generate.cpp:20170-20175`）。
- DFlash2 drafter が選択・利用され、`begin_request` が実行されること。DFlash2 が使われない request、または別の drafter を使う場合にはこのログは出ない（CUDA: `engine/src/program/generate.cpp:20170-20175`、SYCL: `engine/sycl/src/program/generate.cpp:11105-11109`）。
- リングログが有効であること。`STRATA_DF2_RING_LOG` の値が `0` で始まる場合は無効。CUDA 系・SYCL 系ともリングログの staging 確保失敗時も無効となり、別の stderr メッセージを出す（CUDA: `engine/src/core/dflash2.cpp:822-834`、SYCL: `engine/sycl/src/core/dflash2.cpp:215-225`）。
- request の再開範囲が空なら `rebuild` が呼ばれず、欠落位置行は出ない。リングログが有効であれば統計行は `rebuild` の有無にかかわらず `begin_request` の末尾で出る（CUDA: `engine/src/core/dflash2.cpp:970-977,1007-1022`、SYCL: `engine/sycl/src/core/dflash2.cpp:648-655,685-700`）。
- CLI 引数や別環境変数による本変数の値の上書きは実装中にない。`STRATA_DF2_RING_LOG` はリングログ機能を止める別設定であり、そのとき本変数のログも出ない。

## 実行時の詳細

request ごとの `begin_request` は、再利用する履歴とリングログを照合し、必要な範囲を `rebuild` で復元する。復元できない位置があると `missing` に数え、設定有無をその位置ごとに調べて最初の 8 件まで stderr に記録する。`begin_request` の末尾で、関数ローカル `static const bool verbose` が true なら、リングログ容量・履歴長・退避 lineage 数・復元行数・欠落数・所要時間を stderr に 1 行出す（CUDA: `engine/src/core/dflash2.cpp:891-903,1007-1022`、SYCL: `engine/sycl/src/core/dflash2.cpp:585-597,685-700`）。

統計行の設定有無は、各 build の `begin_request` がこの static 初期化に初めて到達した時点で一度だけ読み取られ、その後の request でも同じ値が使われる。初回到達後に環境を変更しても統計行の on/off は変わらない。一方、欠落位置行の `getenv` は `rebuild` 内で対象位置ごと（ただし各 rebuild の最初の 8 欠落まで）に評価されるため、その判定は static cache されない（上記行番号）。

## ログと測定値

設定ありの場合、stderr に次の形式で出る。各 rebuild で欠落した最初の 8 位置までの個別行と、再構築処理を通った request ごとの統計行である。

```text
strata dflash2 ring: position %lld was never logged (hist %zu)
strata dflash2 ring: request %lld resume %lld of %lld: live log %.1f MiB (%lld positions), parked %zu lineages %.1f MiB, rebuilt %lld rows (missing %lld) in %.2f ms%s
```

リング再構築自体が失敗した場合は、この変数の値に関係なく `strata dflash2: %s: the ring starts over for this request` も stderr に出る（CUDA: `engine/src/core/dflash2.cpp:1011-1015`、SYCL: `engine/sycl/src/core/dflash2.cpp:688-694`）。生成側は復元行数がある場合に別の serve ログを出し、欠落が 64 行以上の cold request ではドラフトについての説明を出す。生成側コメントと文言は、そのときの回答は同じとしている（CUDA: `engine/src/program/generate.cpp:20175-20182`、SYCL: `engine/sycl/src/program/generate.cpp:11109-11116`）。この変数自体は統計ログを追加し、終了・失敗条件を変更しない。測定値は本変数についての Strata 資料に見当たらない。

## 根拠

- 候補名の全参照と直接読み取り: `engine/src/core/dflash2.cpp:899,1018`、`engine/sycl/src/core/dflash2.cpp:593,696`。他の参照は設定 UI のメタデータ `terminal/data/settings-register.json:6627`。
- リングログの初期化と無効条件: `engine/src/core/dflash2.cpp:822-834`、`engine/sycl/src/core/dflash2.cpp:215-225`。
- DFlash2 request 呼び出し条件と観測ログ: `engine/src/program/generate.cpp:20170-20185`、`engine/sycl/src/program/generate.cpp:11105-11118`。
- 関連資料 `docs/DETAILS.md` の DFlash2 記述（`1237`, `1591-1595`）には、この統計環境変数の挙動や測定値の記載はない。
