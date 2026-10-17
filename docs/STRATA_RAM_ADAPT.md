# `STRATA_RAM_ADAPT`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。

## 役割

`--serve` の decode 中、常駐 RAM コピーに保持する expert の一部を、会話中の routing 実績に合わせて入れ替えます。GPU に載っていない expert のうち、今後よく使われる候補をファイルから RAM へ読み、同じ層の RAM 常駐 expert のうち使われていないものの場所に置きます。これにより、後続 window がその expert を参照するときのファイル読み出しを避けられる場合があります。

これは RAM コピー内の入れ替え数の上限です。GPU の residency、routing、重み、GPU 側 adaptive tier の選択規則は変更しません。常駐 RAM モードでない場合は効果がありません。

## 値と判定

値は `std::atoi` で整数に変換し、結果を `max(0, 値)` で下限 0 に制限します。文字列全体の厳密な数値検証はありません。

| 環境変数 | 結果 |
|---|---|
| 未設定 | 0（無効） |
| 空文字、数字で始まらない値 | `atoi` の結果 0（無効） |
| 正の整数 | その数を候補入れ替え数の上限として使用 |
| `0`、負数 | 0（無効） |
| 数字の後ろに文字が続く値 | `atoi` が読めた先頭の整数を使用（例: `3abc` は 3） |

先頭の空白と符号は `atoi` の変換規則に従います。値は関数内の `static const int` に保存され、プロセスで初めてこの decode 経路に到達したときに評価されます。その後の環境変更は反映されません（`src/program/generate.cpp:14275-14278`）。

## 有効になる条件

値が正でも、各条件を満たす decode window の直前に限り候補選定が行われます。

- 初回 window ではない。
- adaptive tier の利用実績 (`drive.d.usage`) がある。
- 未適用の GPU 側 adaptive swap がない。
- 非同期 adaptive round が動作中でない（非同期機能を使っていないか、状態が idle）。
- 常駐 RAM コピーが準備済み (`src.complement_ready()`)。
- 複数 GPU、peer GPU、remote expert opt-in を使っていない。
- `--batch` が無効（`o.batch == 0`）。

コード上の条件は `src/program/generate.cpp:14279-14281` にあります。層 split、peer/helper GPU、batch では選定ブロックに入りません。`STRATA_EXCHANGE_ROTATE` が有効な場合、`replace_resident()` は失敗を返して変更しないため、この変数による RAM 入れ替えは起きません（`include/strata/core/expert_source.hpp:752-757`, `src/core/expert_source.cpp:3457-3460`）。

## 実行時の詳細

各対象 window の前に層ごとに候補を探します。GPU に載っていない expert (`host_res[e] < 0`) に限り、RAM にない expert の中から decayed usage が 2.0 以上の最大値を `in` として選び、RAM にある expert の中から usage が最小の `out` を探します。`out` の usage が 0.5 未満の場合だけ、その層の入れ替え候補になります。候補の優先度は `usage[in] - usage[out]` で、大きい順に並べ、全層から最大 `n` 件を残します（`src/program/generate.cpp:14282-14299`）。同値の候補は `std::sort` の比較関数で同順位です。

各候補は `FileExpertSource::replace_resident()` に渡されます。妥当性、resident slot、競合する override などを確認した後、対象 expert の blob を一時バッファへファイルから読み、常駐 RAM コピーの `out` の場所へコピーして、resident offset の対応を交換します。読み出しに失敗した場合は置換前の RAM コピーを保ち、その候補は成功扱いになりません。成功数は `ram_adapts_` に累積されます（`src/core/expert_source.cpp:3457-3483`）。呼び出し側は戻り値を使わず、候補ごとの失敗を個別ログには出しません。

この処理は window の間ではなく、その直前に呼び出し元スレッド上で同期実行されます。prompt の初回 window は対象外なので prompt routing から置換候補は作られません。一方、後続の prompt/request は同一プロセスの更新済み RAM コピーを利用し得ます。request の統計出力では成功数が正の場合に `strata serve: resident RAM: %lld experts moved in from the file in place of unused ones (STRATA_RAM_ADAPT)` と表示されます（`src/program/generate.cpp:14766-14768`）。

## 根拠

- 値の読み取り、候補条件・順位付け、置換呼び出し: `src/program/generate.cpp:14268-14302`
- RAM resident コピーの検査、ファイル読み込み、コピー先更新、成功カウント: `src/core/expert_source.cpp:3457-3483`
- 回転ストレージでの非対応条件と API 契約: `include/strata/core/expert_source.hpp:752-758`
- ログ: `src/program/generate.cpp:14759-14768`
- `docs/DETAILS.md:162-190` も `--serve`・一 GPU の opt-in と条件を説明し、RTX 3060 12 GB / 32 GB RAM / IQ2_XS の記載試行で decode 43.26→50.40 tok/s としています。この値は同資料に記載された単一環境・単一量子化の測定結果であり、一般的な性能保証ではありません。
