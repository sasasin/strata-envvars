# `STRATA_LOOKUP_CHAIN_FIXED`

調査対象: Strata `main` の HEAD `d46f5f268f8ed797e83a5c63a69bffbd7a581cf6`（`2026-11-25` 時点）。

## 役割

lookup-chain が prompt lookup から追加した候補を `DraftPolicy::chain` で選別するかを切り替える。未設定なら、MTP draft の確率と lookup の match 長、窓幅ごとの推定コストから追加候補数を決める。設定されていればその選別を通さず、見つかった候補数を後続の上限処理まで保持する。候補生成を有効にするスイッチではなく、生成 token の採否を直接変えるものでもない。CUDA/HIP の生成処理と SYCL の生成処理に実装がある（`engine/src/program/generate.cpp:21751,22771-22782,25067-25080`、`engine/sycl/src/program/generate.cpp:11722,12715-12729,14077-14090`）。

## 値と判定

数値や文字列の内容は parse せず、`std::getenv(...) != nullptr` で設定有無だけを見る。従って空文字 `""` も設定扱いとなり、`0`、`1`、`true`、`false`、空白を含む文字列など、環境変数が存在すればすべて同じ分岐になる。境界値や無効値の概念はなく、大小文字も比較しない。未設定時が通常のコスト選別あり、設定時は選別を飛ばす（同 `generate.cpp:21751,22778-22782,25073-25076`、SYCL 同 `generate.cpp:11722,12722-12726,14083-14086`）。

| 実装経路 | unset | 設定時に有効になる値 | 設定時に無効になる値 |
|---|---|---|---|
| CUDA/HIP server と SYCL server | policy による候補数選別あり | 空文字を含む、存在するすべての値 | なし。値の内容は検査しない |
| CUDA/HIP と SYCL の通常生成ループ | policy による候補数選別あり | 空文字を含む、存在するすべての値 | なし。値の内容は検査しない |

## 有効になる条件

- 実際に lookup-chain 候補を作る条件が満たされる必要がある。`--lookup-chain K` が 0 より大きく、初回 window でなく、suffix lookup をその window で採用しておらず、既存 window に余地がある場合に候補を検索する。server の CUDA/HIP 経路ではさらに `draft_on`、SYCL の MTP 経路では `use_mtp` が必要（`engine/src/program/generate.cpp:22771-22776,25067-25072`、`engine/sycl/src/program/generate.cpp:12715-12720,14077-14082`）。
- `--lookup-chain` の K が候補数の上限であり、`--lookup-chain-min` が候補を継ぐための最低 match 長を決める。CLI parser は K を 0–7 に clamp し、最低 match 長を 3 以上にする（CUDA/HIP: `engine/src/program/generate.cpp:4125-4126`、SYCL: `engine/sycl/src/program/generate.cpp:2099-2100`）。環境変数はこれらの引数を上書きせず、K=0 なら環境変数が設定されていても候補生成は起きない。
- backend / build macro ごとの値の parse 差はない。名前を読むのは CUDA/HIP 側の `engine/src/program/generate.cpp` と SYCL 側の独立した `engine/sycl/src/program/generate.cpp`。それぞれの server / 通常生成経路に判定がある。
- policy 選別を飛ばしても、候補数は先に空き window と K で制限される。CUDA/HIP server では `--lookup-max-t` による graph fit が追加で候補を減らすことがある（`engine/src/program/generate.cpp:22783-22787`）。

## 実行時の詳細

server 経路では `chain_fixed` を関数内 `static const bool` として初期化するため、プロセス内の最初の初期化時に一度だけ読み取る。初期化後に同一プロセス内で環境を変更しても反映されない。CUDA/HIP server はこの値を各対象 window で使い、候補が 1 件以上なら未設定時だけ `policy.chain(T, p_mtp, chain_n, cm)` を呼ぶ（`engine/src/program/generate.cpp:21746-21752,22771-22782`）。SYCL server も同じ構造である（`engine/sycl/src/program/generate.cpp:11717-11723,12715-12726`）。

通常生成ループ側は `chain_n > 0` の分岐で `getenv` を直接呼び、各 eligible window で設定有無を調べる。未設定なら MTP draft の確率積 `p_mtp` と match 長 `cm` を policy に渡す。設定時は policy を呼ばず、lookup が返した `chain_n` をそのまま後続へ渡す（CUDA/HIP: `engine/src/program/generate.cpp:25065-25080`、SYCL: `engine/sycl/src/program/generate.cpp:14075-14090`）。`DraftPolicy::chain` は候補数、最大窓幅、match による推定受理率、測定済み窓コストと margin を使って追加数を 0 から選ぶ（`engine/src/spec/draft_policy.cpp:1002-1032`）。

選ばれた lookup token は MTP 等の draft の後ろに検証 window として並べられ、通常の verifier が検証する（CUDA/HIP: `engine/src/program/generate.cpp:22797-22807`、SYCL: `engine/sycl/src/program/generate.cpp:14089-14104`）。この環境変数は候補の採否を強制せず、Verifier の受理処理を迂回しない。server の追加候補は `DONE` の lookup-chain counters に含まれ、最後に stderr に集計行が出る。環境変数固有の警告・終了経路はない（CUDA/HIP: `engine/src/program/generate.cpp:23551-23564,23926-23928`、SYCL: `engine/sycl/src/program/generate.cpp:13114-13132,13264-13266`）。

## ログと測定値

Server では lookup-chain が有効（`--lookup-chain > 0`）なら、stderr に `strata serve: lookup chain: %lld of %lld windows, %lld of %lld chained drafts accepted` と出る。通常生成では stdout に `lookup chain` として windows 数・受理候補数を表示する。これらは実際に採用・受理された数の集計で、環境変数の設定値や policy bypass の有無は表示しない（`engine/src/program/generate.cpp:23926-23928`、`engine/sycl/src/program/generate.cpp:14254-14256`）。本変数の設定有無を比較した測定値は記載しない。

## 根拠

- `engine/src/program/generate.cpp:21746-21752,22769-22787,23551-23564,23926-23928,25065-25080`
- `engine/sycl/src/program/generate.cpp:11717-11723,12713-12729,13114-13132,13264-13266,14075-14090,14254-14256`
- `engine/src/spec/draft_policy.cpp:1002-1032`
- `engine/src/program/generate.cpp:4125-4126`; `engine/sycl/src/program/generate.cpp:2099-2100`
