# `QSA_MROPE`

調査対象: Strata `main` の HEAD `477ac13cbe8e582c20484871ce459d20d82df09d`（2026-10-17 時点）。外部ライブラリの環境変数は対象外。

## 役割

候補一覧にある名前ですが、製品の Strata 実行経路が読む環境変数ではありません。リポジトリ内で `getenv("QSA_MROPE")` を呼ぶのは Metal の `qsa_parity` 検証プログラムだけです。このテストで `qsa_prep` の M-RoPE function constant を有効にし、位置テーブルを使う経路を検証します。通常の Strata サーバーや Metal エンジンの挙動をこの環境変数で切り替える根拠はありません。

## 値と判定

`metal/tests/qsa_parity.cpp` は値の内容ではなく、`getenv()` が null かどうかで M-RoPE を有効にします。未設定なら無効、設定されていれば有効です。したがって空文字、`0`、`false` を含むどの文字列でも有効になります。値を数値や真偽値として parse する処理はありません。

設定値が厳密に小文字の `id` と一致すると、テスト用 M-RoPE テーブルに各 cell の同じ番号を3軸分設定します。それ以外の設定値では固定 seed の乱数からテーブルを生成します。大文字小文字や前後の空白を除去する処理はありません。環境変数は `main()` 内で一度読み、関数内キャッシュや後続の再読込はありません。

| `QSA_MROPE` | function constant 24 | テスト用位置テーブル |
|---|---|---|
| unset | false | 未使用の通常 RoPE 経路 |
| 設定、値が `id` 以外 | true | 固定 seed による疑似乱数の (t, h, w) 位置 |
| 設定値が厳密に `id` | true | 各 cell の identity 位置。通常 RoPE との一致確認用 |

## 有効になる条件

この環境変数の効果は Metal の `qsa_parity` 検証プログラムに限られます。検証プログラムを実行しない通常の Strata 起動では参照されません。GPU/Metal の実行環境が必要なテストですが、ここではビルドや実行による結果確認はしていません。

製品側にも同名の Metal function constant `QSA_MROPE`（番号24）はありますが、これは環境変数ではありません。Metal エンジンは `g_mrope_host != nullptr` から状態を決め、function constant とパイプライン名を設定します。画像入力の位置テーブルがないときは function constant を設定せず、あるときは M-RoPE 版を使います。したがって製品側の条件はモデル入力状態に基づき、`QSA_MROPE` 環境変数の有無ではありません。

## 実行時の詳細

テストでは環境変数の有無を function constant 24 に渡して `qsa_prep` パイプラインを作成します。設定時には buffer 20 の int32 `[cells][3]` テーブルを結合します。`id` 以外は seed 77 の乱数で各軸の位置を埋め、`id` の場合は軸ごとに cell 番号を入れます。CPU 参照計算も同じテーブルを用い、M-RoPE 時は回転ペア `i` の位置として `tab[cell * 3 + i % 3]` を使います。テストは prep の出力などを CPU 参照値と照合し、失敗数に応じた終了コードと `PASS` / `FAIL` 表示を出します。

カーネルでは function constant が有効な場合に M-RoPE テーブルの位置を参照します。通常の Strata エンジンでは `window.cpp` の `mrope_on()` がグローバル画像位置テーブルの存在を調べ、`qsa_c()` が function constant 24 を設定し、`qsa_k()` が対応するパイプライン variant を選びます。`qsa_prep` の dispatch は M-RoPE バッファを buffer 20 に渡します。これは画像を含む入力向けの実装経路です。

## 根拠

- 環境変数の読み取り、function constant 設定、値 `id` の判定、テストテーブル生成: `metal/tests/qsa_parity.cpp:30-47,68-79`。
- テスト側 CPU 参照での M-RoPE 位置選択と検証: `metal/tests/qsa_parity.cpp:168-220`。
- カーネルの function constant 定義と M-RoPE テーブル仕様: `metal/kernels/qsa.metal:31-37,85-96`。
- 製品エンジン側の判定と function constant / pipeline 選択: `metal/src/engine/window.cpp:363-383,723-732`。
- 画像入力と interleaved M-RoPE の説明: `docs/DETAILS.md:1708-1711`。
