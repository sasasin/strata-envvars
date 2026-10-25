# `STRATA_LOOKUP_CHAIN_FIXED`

調査対象: Strata `main` の HEAD `7695859aa13afb248bdb4d36f9b2e95707db079d`（2026-10-13 時点）。外部ライブラリの環境変数は対象外。

## 役割

`--lookup-chain` が見つけた追加 draft を、オンラインの `DraftPolicy` に選別させず、そのまま検証 window に追加します。通常は、その機械で測った window 時間と、MTP draft の確率・lookup chain の過去の受理率から、追加する token 数を `policy.chain()` が選びます。この変数を設定するとその選別を飛ばし、見つかった chain proposal をすべて候補に残します。これは検証前の draft window 長を変える設定であり、変数を設定しただけで lookup chain 自体を有効にはしません。

## 値と判定

コードは値を parse せず、`std::getenv("STRATA_LOOKUP_CHAIN_FIXED") != nullptr`（または同等の `== nullptr` 判定）だけを見ます。したがって値が未設定なら通常の適応選別を行い、値が設定されていれば空文字を含む任意の文字列で選別を無効にします。`0`、`false` も設定済みなので有効化側です。数値範囲、大文字小文字、文字列全体の検証はありません。

| 状態 | chain proposal がある場合の処理 |
|---|---|
| 未設定 | `policy.chain(T, p_mtp, chain_n, cm)` で追加数を選ぶ |
| 設定あり（空文字を含む） | `policy.chain()` を呼ばず、`propose_from_sources()` の戻り値 `chain_n` を維持する |

## 有効になる条件

- `--lookup-chain K` が正の値で指定されていること。CLI parser は `atoi` の結果を `0..7` に clamp し、既定値は `0` です。`--lookup-chain` が無効なら、この環境変数に効果はありません。
- lookup-chain を追加できるだけの window の余地があり、初回 window ではなく、suffix draft が採用されていないこと。
- サーバーの逐次 decode 経路では、lookup chain が提案 (`chain_n > 0`) されたときに限り、未設定時だけ `DraftPolicy::chain()` による選別を実行します。単発 `strata generate` の MTP 経路でも同じ条件で選別を飛ばします。
- サーバー経路の提案元は過去の context と MTP draft をつないだ tail を使い、`--lookup-chain-min` 以上の一致から最大 K 個を探します。`--lookup-chain-min` の既定値は 3 で、parser は下限 3 に clamp します。

CLI の `--lookup-chain` は MTP がない場合にも prompt lookup chain を使う経路があります。MTP がないと `T` は 1 で始まるため、その提案の後段に同じ環境変数の判定があります。最大 window は `--lookup-chain` と現在の verify 上限で制限されます。なお、この環境変数が作用するのは chain proposal の選別箇所であり、suffix-draft の `policy.choose()` には作用しません。

## 実行時の詳細

CUDA と SYCL の双方に同等の実装があります。サーバー decode では `chain_fixed` を関数内の `static const bool` として初期化するため、プロセス内でその関数が最初に通った際の環境状態を保持します。その後のリクエスト中やリクエスト間で環境を書き換えても再判定されません。単発 `strata generate` の別経路は chain proposal ごとに `getenv()` を直接呼ぶため、その箇所では毎回判定します。

採用された `chain_n` は MTP window の後ろに連結され、検証 window のサイズ `T` に加算されます。サーバーは各要求の `strata serve: lookup chain: ...` 行に chain を使った window 数と、chain draft の受理数を表示します。単発生成は最終統計の `lookup chain` 行に window 数と受理数を表示します。設定値を読み取っただけの専用ログはありません。

## 根拠

- `src/program/generate.cpp:660-665, 809-812, 2040-2041`: CLI option の既定値、help、`--lookup-chain` / `--lookup-chain-min` の parse と範囲。
- `src/program/generate.cpp:2474-2478`: lookup chain 有効時の verify window 上限拡張。
- `src/program/generate.cpp:11128, 11830-11846`: サーバー経路の静的 env 判定、proposal、policy gate と window 延長。
- `src/program/generate.cpp:13030-13045`: 単発 generate の proposal、都度の env 判定、window 延長。
- `sycl/src/program/generate.cpp:10386, 11122-11138, 12328-12344`: SYCL サーバー／単発経路の対応実装。
- `include/strata/spec/draft_policy.hpp:38-44`: `chain()` が候補数を適応選択し、chain 結果を観測する API。
- `src/program/generate.cpp:12369-12371, 13180-13185`: サーバーと単発生成の lookup-chain 集計表示。
- `docs/DETAILS.md:275-277`: CLI の `--lookup-chain-min` の説明はあるが、この環境変数の記載はありません。
