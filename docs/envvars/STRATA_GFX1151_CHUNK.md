# `STRATA_GFX1151_CHUNK`

調査対象: Strata `main` の HEAD `7dd5cf18e68c639a8773e096c5c79f971ea2a9f5`（2026-10-25 時点）。

## 役割

Windows HIP で `--prefill auto` を指定したとき、gfx1151（Strix Halo）の統合 GPU 環境に限り、既定の自動チャンク上限6144を8192へ戻します。通常の Windows HIP では、大きなチャンクによる commit charge 問題を避けるため、裸の `auto` は6144に制限されます。この変数はその制限を外すための起動時フックです。

## 値と判定

`src/program/generate.cpp` は `getenv()` で設定有無を確認し、値全体は parse しません。`STRATA_GFX1151_CHUNK` が設定されていて、先頭文字が `0` なら上限変更を抑止します。それ以外は変更を許可します。

| `STRATA_GFX1151_CHUNK` | 判定 |
|---|---|
| 未設定 | 変更を許可 |
| `0`、`0anything` | 変更を抑止 |
| `1`、`false`、空文字、その他の文字列 | 変更を許可 |

空白や大文字小文字、数値としての妥当性は検査されません。さらに同じ分岐で `STRATA_GFX1151_DEFAULTS` の先頭文字も検査し、こちらが `0` の場合も変更を抑止します。両方の値が判定対象になるのは下記の適用条件を満たすときだけです。根拠: `src/program/generate.cpp:2827-2833`。

## 有効になる条件

次の条件が必要です。

- `STRATA_USE_HIP` でビルドされた Windows 実行ファイルである。
- GPU 0 のプロパティ取得が成功し、GPU 0 が統合 GPU と報告される。
- 検出できた全 GPU が統合 GPU で、GPU 0 と同じアーキテクチャ名の先頭7文字を持つ。GPU 数の取得に成功した場合、後続 GPU も検査される。
- GPU 0 の `gcnArchName` が `gfx1151` で始まる。
- CLI が裸の `--prefill auto` である。`--prefill 8192`、`--prefill auto:N`、または `STRATA_PREFILL_AUTO_MAX` が設定された `--prefill auto` には適用されない。
- `STRATA_GFX1151_CHUNK` と `STRATA_GFX1151_DEFAULTS` のどちらも、先頭文字が `0` ではない。

HIP 以外のビルド、Linux、別アーキテクチャ、離散 GPU を含む環境、および明示的なチャンク指定では、この分岐は変更を行いません。根拠: `src/program/generate.cpp:2796-2835`。

## 実行時の詳細

`--prefill` の解析時、`auto` は通常8192を初期値にします。Windows HIP の裸の `auto` では `host_limits::auto_chunk_cap()` が6144を返し、上限と初期チャンクが6144になります。後続の HIP 起動時処理で対象環境と判定された場合、この上限を0（上限なし）に戻し、初期チャンクを少なくとも8192にします。その後の自動計画は expert cache などの容量に合わせてチャンクを選ぶため、8192未満になる場合があります。この変数は8192を強制する指定ではなく、6144の既定上限を外す指定です。

`STRATA_PREFILL_AUTO_MAX` の判定は設定値ではなく設定有無です。たとえ空文字でも設定されていると `bare_auto` ではなくなり、この gfx1151 分岐の条件を満たしません。`--prefill auto:N` も同様に対象外です。読み取りは `generate` の起動時にオプションを構成する処理の中で行われ、環境変数をリクエストごとに再評価するコードはこの分岐にはありません。

この変数専用のログ出力はありません。Windows HIP の安全上限6144、ユーザー指定の8192以上のチャンクに対する警告条件は `include/strata/platform/host_limits.hpp:19-30` に定義されていますが、裸の `auto` を gfx1151 用に上限解除する経路ではユーザー指定チャンク向けの警告条件には入りません。

## 根拠

- `src/program/generate.cpp:2574-2598` — `--prefill`、`STRATA_PREFILL_AUTO_MAX`、Windows HIP の6144上限、bare 判定。
- `include/strata/platform/host_limits.hpp:19-30` — 上限値6144およびユーザー指定チャンクの警告条件。
- `src/program/generate.cpp:2796-2835` — HIP 起動時のGPU検査と `STRATA_GFX1151_CHUNK` / `STRATA_GFX1151_DEFAULTS` 判定、8192への変更。
- `src/program/generate.cpp:7594-7657, 7673-7693` — 自動チャンクの上限と、利用可能な cache 容量に応じた選択。
- `docs/release-notes-0.2.3.md:5` — 0.2.2との比較として記載されたWindows gfx1151の測定条件・結果。これはリリースノートの報告値であり、本調査で再測定したものではありません。
