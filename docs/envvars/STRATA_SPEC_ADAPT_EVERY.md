# `STRATA_SPEC_ADAPT_EVERY`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。外部ライブラリの環境変数は対象外。

## 役割

投機的デコード開始直後の適応 expert tier の更新間隔を指定します。適応 tier は routing 使用量に応じて VRAM 上の expert を入れ替える機能です。通常の間隔は `--adapt-every`（既定 4 verify rounds）ですが、この変数が有効なら、最初の `STRATA_SPEC_ADAPT_WARM` verify rounds に限り短い間隔を使います。以降は通常の `--adapt-every` 間隔に戻ります。

この環境変数単独では適応 tier を有効にしません。`--spec >= 2`、適応 tier が有効であること、および後述する値の条件が必要です。

## 値と判定

値は `std::atoi()` で整数へ変換されます。文字列全体の妥当性検査はなく、先頭の空白と符号を含む整数部分を読み、整数の後ろにある文字列は無視します。空文字や数値に変換できない文字列は 0 になります。変換結果が `n` として採用されるのは、`n > 0` かつ `n < --adapt-every` の場合だけです。

| 入力・状態 | 結果 |
|---|---|
| 未設定 | `n=0`。この変数による短縮間隔は設定されない。ただし後述の NVIDIA sm_86 opt-in 時は、起動時に unset の変数へ `2` が設定される |
| 空文字、0、負数、数値で始まらない文字列 | `atoi()` の結果が 0 以下となり、短縮間隔を設定しない |
| 正数で始まる値（例 `2`, `2foo`, `  +2`） | 数値部分を変換し、通常間隔より小さく、かつ正なら採用 |
| `n >= --adapt-every` | 採用しない。通常間隔のまま |
| `--adapt-every` を明示指定 | 環境変数を評価しない。明示指定の有無で判定を飛ばす |

短縮間隔を設定するには、`STRATA_SPEC_ADAPT_WARM` も `std::atoll()` で正数に変換される必要があります。変換結果が 0 以下なら `STRATA_SPEC_ADAPT_EVERY` の正数値も使われません。`atoi` / `atoll` の表現範囲外の値について、コードは個別のエラー処理をしていません。

## 有効になる条件

- `generate` が CUDA backend で動き、可視 CUDA device がすべて同じ compute capability の場合、起動時に `apply_spec_adapt_default()` が呼ばれます。HIP と Metal のビルドではこの既定値設定経路は呼ばれません。
- この既定値設定関数は compute capability が 8.6（sm_86）のときだけ処理します。さらに `STRATA_SPEC_ADAPT_SM86` の先頭文字が `1` であり、`STRATA_SM86_PERF` の先頭文字が `0` でないことが必要です。`STRATA_SM86_PERF` が unset なら停止条件にはなりません。
- 条件を満たした場合、`STRATA_SPEC_ADAPT_EVERY` が未設定のときだけ値 `2` を設定します。明示設定は空文字を含めて保持されます。`STRATA_SPEC_ADAPT_WARM` が未設定なら同様に `200` を設定します。
- 実際の利用には `--adapt-every` が明示されておらず、`--spec >= 2` で、通常の `adapt_every > 0` かつ `adapt_swaps > 0` であることも必要です。明示した `--adapt-every` は環境値より優先され、warm 間隔は適用されません。
- 対象箇所の条件を満たさない場合（例: `--spec < 2`、非 sm_86 CUDA、混在 compute capability、opt-in なし）は、環境変数が設定されていてもこの短縮間隔は有効になりません。ただし `STRATA_SPEC_ADAPT_EVERY` の読み取り自体は speculative 条件を満たすと行われます。

## 実行時の詳細

環境変数の既定値注入は GPU compute capability の確認時に行われます。`generate.cpp` はその後、コマンドライン引数を処理した後の設定構築段階で `STRATA_SPEC_ADAPT_EVERY` と `STRATA_SPEC_ADAPT_WARM` を読みます。環境を読むたびに値を変換し、static cache は使いませんが、設定値を `o.adapt_warm_every` と `o.adapt_warm_rounds` に格納するのはこの設定構築時の一度です。実行開始後の環境変更はその実行中の間隔に反映されません。

投機的デコードの適応処理では verify round 番号 `rounds` に対し、`rounds < adapt_warm_rounds` の間は `adapt_warm_every`、それ以降は `adapt_every` を選びます。適応処理は usage table が空でなく、`adapt_every > 0` で、round が選ばれた間隔で割り切れ、pending 交換がない場合に起動します。したがって変数が有効な場合、最初の更新は通常間隔より早くなり、その後も warm 区間中は短い周期で更新されます。

この変数専用のログは見当たりません。実行後の `adaptive tier` 統計行は swap 総数と通常の `o.adapt_every` を表示するため、warm 区間で実際に使った間隔はその行からは分かりません。

## 根拠

- `src/core/nv_defaults.cpp:73-91`: sm_86、`STRATA_SPEC_ADAPT_SM86`、`STRATA_SM86_PERF` の条件と、unset の場合に限る `2` / `200` の注入。
- `src/program/generate.cpp:2838-2853`: CUDA の非 HIP / 非 Metal 経路で、全可視 device の compute capability が同じ場合に既定値関数を呼ぶ。
- `src/program/generate.cpp:688-694`: 通常間隔の既定値 4、warm 区間の設定項目、round ごとの間隔選択。
- `src/program/generate.cpp:3220-3229`: `--adapt-every` 明示指定と `--spec` 条件、`atoi` / `atoll` による値変換、採用条件。
- `src/program/generate.cpp:14442-14453`: speculative decode の適応処理が選択間隔で起動する条件。
- `src/program/generate.cpp:16781-16783`: 終了時の統計行が通常の `adapt_every` を表示する。
- HEAD の Markdown 文書にはこの環境変数の詳細な挙動や測定条件を説明する資料は見当たらなかったため、性能値や速度向上は記載していない。
